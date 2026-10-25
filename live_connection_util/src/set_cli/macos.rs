use anyhow::{Result, ensure};
use objc2::{class, msg_send, rc::Retained, runtime::AnyObject};
use objc2_foundation::{NSArray, NSDate, NSRunLoop, NSString};
use std::{
    path::Path,
    process::Command,
    time::{Duration, Instant},
};

#[link(name = "AppKit", kind = "framework")]
unsafe extern "C" {}

#[link(name = "CoreGraphics", kind = "framework")]
unsafe extern "C" {
    fn CGGetActiveDisplayList(max: u32, displays: *mut u32, count: *mut u32) -> i32;
    fn CGDisplayIsBuiltin(display: u32) -> u32;
}

pub const TD_APP: &str = "/Applications/TouchDesigner.app";
pub const BITWIG_APP: &str = "/Applications/Bitwig Studio.app";

pub fn external_displays() -> Result<usize> {
    let mut displays = [0_u32; 32];
    let mut count = 0;
    // CoreGraphics writes at most the supplied buffer length.
    let status = unsafe { CGGetActiveDisplayList(32, displays.as_mut_ptr(), &mut count) };
    ensure!(
        status == 0,
        "Could not inspect displays: CoreGraphics {status}"
    );
    Ok(displays[..count as usize]
        .iter()
        .filter(|&&id| unsafe { CGDisplayIsBuiltin(id) == 0 })
        .count())
}

fn applications(bundle: &str) -> Retained<NSArray<AnyObject>> {
    let bundle = NSString::from_str(bundle);
    // NSRunningApplication's documented class method returns this array type.
    unsafe {
        msg_send![class!(NSRunningApplication), runningApplicationsWithBundleIdentifier: &*bundle]
    }
}

pub fn running(bundle: &str) -> bool {
    let apps = applications(bundle);
    (0..apps.count()).any(|index| {
        let app = apps.objectAtIndex(index);
        let terminated: bool = unsafe { msg_send![&*app, isTerminated] };
        !terminated
    })
}

pub fn td_pids() -> Vec<i32> {
    // Refresh AppKit's cached process state before deciding whether opening is safe.
    NSRunLoop::currentRunLoop().runUntilDate(&NSDate::dateWithTimeIntervalSinceNow(0.01));
    let apps = applications("ca.derivative.TouchDesigner");
    (0..apps.count())
        .filter_map(|index| {
            let app = apps.objectAtIndex(index);
            let terminated: bool = unsafe { msg_send![&*app, isTerminated] };
            (!terminated).then(|| unsafe { msg_send![&*app, processIdentifier] })
        })
        .collect()
}

pub fn wait_for_bitwig() -> Result<()> {
    let deadline = Instant::now() + Duration::from_secs(120);
    loop {
        super::check_cancelled()?;
        let apps = applications("com.bitwig.studio");
        let ready = (0..apps.count()).any(|index| {
            let app = apps.objectAtIndex(index);
            let finished: bool = unsafe { msg_send![&*app, isFinishedLaunching] };
            let terminated: bool = unsafe { msg_send![&*app, isTerminated] };
            finished && !terminated
        });
        if ready {
            return Ok(());
        }
        ensure!(
            Instant::now() < deadline,
            "Bitwig did not finish launching within 120 seconds; remaining projects were not opened"
        );
        // NSRunningApplication state refreshes when the current run loop runs.
        NSRunLoop::currentRunLoop().runUntilDate(&NSDate::dateWithTimeIntervalSinceNow(0.1));
    }
}

pub fn open(app: &str, file: &Path) -> Result<()> {
    super::check_cancelled()?;
    let status = Command::new("/usr/bin/open")
        .args(["-g", "-a", app])
        .arg(file)
        .status()?;
    ensure!(
        status.success(),
        "Could not open {} with {app}: {status}",
        file.display()
    );
    Ok(())
}
