uniform float vignetteStrength; // 0.0 = none, 1.0 = full vignette
uniform float vignetteScale;    // Controls how quickly vignette falls off

out vec4 fragColor;

void main()
{
    vec4 baseColor = texture(sTD2DInputs[0], vUV.st);
    vec2 uv = clamp(vUV.st, 0.0, 1.0);

    // Frame-shaped falloff: avoids a visible circular spotlight in wide output.
    vec2 edge = uv * (1.0 - uv);
    float frame = clamp(edge.x * edge.y * max(vignetteScale, 0.0), 0.0, 1.0);
    float falloff = 1.0 - pow(frame, 0.25);

    float strength = clamp(vignetteStrength, 0.0, 1.0);
    float vignette = 1.0 - 0.45 * strength * falloff;

    vec3 finalColor = baseColor.rgb * vignette;
    fragColor = TDOutputSwizzle(vec4(finalColor, baseColor.a));
}
