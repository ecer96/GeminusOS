// Geminus Tubes
// Tubitos de color tipo mascara de fosforo: columnas R/G/B separadas por
// huecos negros y scanlines horizontales.
precision highp float;

uniform sampler2D u_texture;
uniform vec4 u_texture_size;   // (1/w, 1/h, w, h)
uniform vec2 u_target_size;
varying vec2 v_texcoord;

void main()
{
    vec3 src = texture2D(u_texture, v_texcoord).rgb;

    // Cada tubo ocupa 2 pixeles de salida; ciclo R, G, B.
    float x = gl_FragCoord.x;
    float tube = mod(floor(x * 0.5), 3.0);
    vec3 mask = vec3(0.18);
    if (tube < 1.0)      mask.r = 1.0;
    else if (tube < 2.0) mask.g = 1.0;
    else                 mask.b = 1.0;

    // Hueco negro entre tubitos.
    float u = mod(x, 2.0);
    float gap = smoothstep(0.0, 0.22, u) * smoothstep(0.0, 0.22, 2.0 - u);

    // Scanlines horizontales con onda triangular (sin trigonometria).
    float sy = fract(v_texcoord.y * 192.0);
    float scan = 0.84 + 0.16 * (1.0 - 2.0 * abs(sy - 0.5));

    // Los tubos realzan su color y dejan pasar algo del resto para no
    // perder detalle en zonas oscuras.
    vec3 col = src * (0.42 + 0.58 * mask) * (0.30 + 0.70 * gap) * scan;
    col *= 1.04;

    gl_FragColor = vec4(col, 1.0);
}
