use crate::{
    config::{Config, select_name},
    latency::{Detector, Timing},
    meter::AudioLevels,
    monitor,
};
use anyhow::{Context, Result, ensure};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::sync::{Arc, mpsc::Sender};

pub fn name(device: &cpal::Device) -> Result<String> {
    Ok(device.description()?.name().to_owned())
}

pub struct Streams {
    _input: cpal::Stream,
    _output: Option<cpal::Stream>,
    stats: Option<Arc<monitor::Stats>>,
    sample_rate: u32,
}
impl Streams {
    pub fn monitor(&self) -> Option<monitor::Reading> {
        self.stats
            .as_ref()
            .map(|stats| stats.reading(self.sample_rate))
    }
    pub fn output_ready(&self) -> bool {
        self.monitor().is_none_or(|r| r.output_frames > 0)
    }
}

pub fn start(
    c: &Config,
    levels: Arc<AudioLevels>,
    timing: Arc<Timing>,
    errors: Sender<String>,
) -> Result<(Streams, String)> {
    let devices: Vec<_> = cpal::default_host().input_devices()?.collect();
    let names: Vec<_> = devices.iter().map(name).collect::<Result<_>>()?;
    let index = select_name(&names, &c.audio_device)?;
    let device = &devices[index];
    let supported = device
        .default_input_config()
        .context("query input format")?;
    ensure!(
        supported.sample_format() == cpal::SampleFormat::F32,
        "input must provide float32 audio; {} offers {:?}",
        names[index],
        supported.sample_format()
    );
    let config = supported.config();
    ensure!(
        c.moog_input <= config.channels && c.tetra_input <= config.channels,
        "{} exposes {} channels, but requested Moog={} Tetra={}",
        names[index],
        config.channels,
        c.moog_input,
        c.tetra_input
    );
    let channels = config.channels as usize;
    let inputs = [c.moog_input as usize - 1, c.tetra_input as usize - 1];
    let (mut monitor_input, output, stats) = if c.no_monitor {
        (None, None, None)
    } else {
        let supported_output = device
            .default_output_config()
            .context("query main output format")?;
        ensure!(
            supported_output.sample_format() == cpal::SampleFormat::F32,
            "main output must provide float32 audio"
        );
        let output_config = supported_output.config();
        ensure!(
            output_config.channels >= 2,
            "interface needs at least two output channels for Main L/R"
        );
        ensure!(
            output_config.sample_rate == config.sample_rate,
            "input/output sample rates must match ({} vs {}); select the same interface clock",
            config.sample_rate,
            output_config.sample_rate
        );
        let output_channels = output_config.channels as usize;
        let (producer, mut consumer, stats) = monitor::pair(
            config.sample_rate,
            c.monitor_buffer_ms,
            inputs,
            c.monitor_gain,
        );
        let output_errors = errors.clone();
        let output = device
            .build_output_stream(
                output_config,
                move |data: &mut [f32], _| consumer.render(data, output_channels),
                move |error| {
                    let _ = output_errors.send(format!("main output: {error}"));
                },
                None,
            )
            .context("open Main L/R output stream")?;
        (Some(producer), Some(output), Some(stats))
    };
    let mut detectors = std::array::from_fn::<_, 2, _>(|_| {
        Detector::new(c.effective_bpm(), c.latency_threshold_db)
    });
    let stream = device
        .build_input_stream(
            config,
            move |data: &[f32], _| {
                let received_us = timing.now_us();
                let peaks = levels.capture(data, channels, inputs);
                if let Some(monitor) = &mut monitor_input {
                    monitor.capture(data, channels);
                }
                for i in 0..2 {
                    detectors[i].process(peaks[i], received_us, &timing, i);
                }
            },
            move |error| {
                let _ = errors.send(error.to_string());
            },
            None,
        )
        .context("open audio input stream")?;
    if let Some(output) = &output {
        output.play().context("start Main L/R output")?;
    }
    stream.play().context("start audio input")?;
    Ok((
        Streams {
            _input: stream,
            _output: output,
            stats,
            sample_rate: config.sample_rate,
        },
        format!(
            "{} / {} ch / {} Hz",
            names[index], channels, config.sample_rate
        ),
    ))
}
