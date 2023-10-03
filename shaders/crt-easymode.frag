uniform vec2 uResolution;
uniform float uFrame;

uniform float MASK_TYPE;
uniform float HALATION;
uniform float DIFFUSION;
uniform float BRIGHTNESS;
uniform float MASK_SIZE;

// All parameter floats need to have COMPAT_PRECISION in front of them
const float GAMMA_OUTPUT = 1.0;
const float MASK_STRENGTH_MIN = 0.2;
const float MASK_STRENGTH_MAX = 0.8;
const float SCANLINE_STRENGTH_MIN = 0.0;
const float SCANLINE_STRENGTH_MAX = 1.0;


const float PI = 3.14159265358979323846;

// compatibility #defines
#define Source sTD2DInputs[0]
#define vTexCoord vUV.st

#define SourceSize vec4(uResolution, 1.0 / uResolution) //either TextureSize or InputSize
#define outsize vec4(uResolution, 1.0 / uResolution)

layout(location = 0) out vec4 fragColor;

vec3 get_scanline_weight(float pos, float beam, float strength)
{
    float weight = 1.0 - pow(cos(pos * 2.0 * PI) * 0.5 + 0.5, beam);
    
    weight = weight * strength * 2.0 + (1.0 - strength);
    
    return vec3(weight);
}

void main()
{
    vec2 tex_size = SourceSize.xy;
    vec2 midpoint = vec2(0.5, 0.5);

    vec2 co = vTexCoord * tex_size * (1.0 / uResolution.xy);
    vec2 xy = co;

    vec2 dx = vec2(1.0 / tex_size.x, 0.0);
    vec2 dy = vec2(0.0, 1.0 / tex_size.y);
    vec2 pix_co = xy * tex_size - midpoint;
    vec2 tex_co = (floor(pix_co) + midpoint) / tex_size;
    vec2 dist = fract(pix_co);

    vec3 col, diff;

    col = texture(Source, xy).rgb;
    diff = texture(Source, xy).rgb;

    float rgb_max = max(col.r, max(col.g, col.b));

    float mask_colors;
    float mask_dot_width;
    float mask_dot_height;
    float mask_stagger;
    float mask_dither;
    vec4 mask_config;

    if      (MASK_TYPE == 1.) mask_config = vec4(2.0, 1.0, 1.0, 0.0);
    else if (MASK_TYPE == 2.) mask_config = vec4(3.0, 1.0, 1.0, 0.0);
    else if (MASK_TYPE == 3.) mask_config = vec4(2.1, 1.0, 1.0, 0.0);
    else if (MASK_TYPE == 4.) mask_config = vec4(3.1, 1.0, 1.0, 0.0);
    else if (MASK_TYPE == 5.) mask_config = vec4(2.0, 1.0, 1.0, 1.0);
    else if (MASK_TYPE == 6.) mask_config = vec4(3.0, 2.0, 1.0, 3.0);
    else if (MASK_TYPE == 7.) mask_config = vec4(3.0, 2.0, 2.0, 3.0);

    mask_colors = floor(mask_config.x);
    mask_dot_width = mask_config.y;
    mask_dot_height = mask_config.z;
    mask_stagger = mask_config.w;
    mask_dither = fract(mask_config.x) * 10.0;

    vec2 mod_fac = floor(vTexCoord * outsize.xy * SourceSize.xy / (uResolution.xy * vec2(MASK_SIZE, mask_dot_height * MASK_SIZE))) * 1.0001;
    int dot_no = int(mod((mod_fac.x + mod(mod_fac.y, 2.0) * mask_stagger) / mask_dot_width, mask_colors));
    float dither = mod(mod_fac.y + mod(floor(mod_fac.x / mask_colors), 2.0), 2.0);

    float mask_strength = mix(MASK_STRENGTH_MAX, MASK_STRENGTH_MIN, rgb_max);
    float mask_dark, mask_bright, mask_mul;
    vec3 mask_weight;

    mask_dark = 1.0 - mask_strength;
    mask_bright = 1.0 + mask_strength * 2.0;

    if (dot_no == 0) mask_weight = mix(vec3(mask_bright, mask_bright, mask_bright), vec3(mask_bright, mask_dark, mask_dark), mask_colors - 2.0);
    else if (dot_no == 1) mask_weight = mix(vec3(mask_dark, mask_dark, mask_dark), vec3(mask_dark, mask_bright, mask_dark), mask_colors - 2.0);
    else mask_weight = vec3(mask_dark, mask_dark, mask_bright);

    if (dither > 0.9) mask_mul = mask_dark;
    else mask_mul = mask_bright;

    mask_weight *= mix(1.0, mask_mul, mask_dither);
    mask_weight = mix(vec3(1.0), mask_weight, clamp(MASK_TYPE, 0.0, 1.0));
    // Too bright otherwise ???
    col /=3;

    col += diff * mask_weight * HALATION;
    col += diff * DIFFUSION;
    col = pow(col, vec3(1.0 / GAMMA_OUTPUT));

    float scanlines = sin(vUV.y * (uResolution.y / 6.0) * 2.0 * 3.14159);
    scanlines = smoothstep(SCANLINE_STRENGTH_MIN, SCANLINE_STRENGTH_MAX, scanlines);
    col *= 1.0 - scanlines * 0.5;

    fragColor = vec4(col, 1.0);
}