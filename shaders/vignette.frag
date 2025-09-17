uniform float vignetteStrength; // 0.0 = none, 1.0 = full vignette
uniform float vignetteScale;    // Controls how quickly vignette falls off

out vec4 fragColor;

void main()
{
    vec4 baseColor = texture(sTD2DInputs[0], vUV.st);
    vec2 p = vUV.st;

    float rawVignette = 0.5 + 0.5 * sqrt(vignetteScale * p.x * p.y * (1.0 - p.x) * (1.0 - p.y));

    // Interpolate between no vignette (1.0) and rawVignette, based on strength
    float vignette = mix(1.0, rawVignette, vignetteStrength);

    vec3 finalColor = baseColor.rgb * vignette;
    fragColor = TDOutputSwizzle(vec4(finalColor, baseColor.a));
}
