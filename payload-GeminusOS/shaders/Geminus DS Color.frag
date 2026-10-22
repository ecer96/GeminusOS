// Geminus DS Color
// Correccion de color tipo pantalla NDS: menos saturacion, gamma y tono
// ligeramente verdoso/calido, sin rejilla.
precision highp float;

uniform sampler2D u_texture;
uniform vec4 u_texture_size;   // (1/w, 1/h, w, h)
uniform vec2 u_target_size;
varying vec2 v_texcoord;

void main()
{
    vec3 c = texture2D(u_texture, v_texcoord).rgb;

    // Aproximacion barata de gamma (sin pow).
    c = c * (1.0 + 0.08 * (1.0 - c));

    // Matriz de color tipo NDS Phat.
    mat3 m = mat3(
        0.87, 0.10, -0.04,
        0.255, 0.645, 0.17,
        0.10, 0.255, 0.73
    );
    c = clamp(m * c, 0.0, 1.0);

    // Menos saturacion y un punto de calidez.
    float lum = dot(c, vec3(0.299, 0.587, 0.114));
    c = mix(vec3(lum), c, 0.86);
    c *= vec3(1.02, 1.00, 0.95);
    c = clamp(c, 0.0, 1.0);

    gl_FragColor = vec4(c, 1.0);
}
