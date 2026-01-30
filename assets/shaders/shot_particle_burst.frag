#version 330

// Shot particle burst effect - bright flash overlay for shots, rockets, and bombs
uniform sampler2D u_frame_texture;
uniform vec2 u_resolution;       // screen resolution in pixels
uniform float u_Time;            // time in seconds
uniform vec2 u_shot_pos;         // shot position in normalized [0,1] screen space
uniform float u_shot_strength;   // 0..1+ (can be > 1 for bombs), fades out
uniform float u_effect_radius;   // radius multiplier (1.0 = shot, 1.5 = rocket, 2.5 = bomb)

in vec2 v_uv;
out vec4 fragColor;

void main() {
    // Sample original color
    vec4 original = texture(u_frame_texture, v_uv);
    
    // Early out if no shot active
    if (u_shot_strength <= 0.001) {
        fragColor = original;
        return;
    }
    
    // Calculate distance from shot position
    vec2 diff = v_uv - u_shot_pos;
    // Correct for aspect ratio
    float aspect = u_resolution.x / max(u_resolution.y, 1.0);
    diff.x *= aspect;
    float dist = length(diff);
    
    // Effect radius - MUCH LARGER for visibility (0.15 base = ~15% of screen)
    float baseRadius = 0.15;
    float maxRadius = baseRadius * u_effect_radius;
    
    // Only apply within radius
    if (dist > maxRadius) {
        fragColor = original;
        return;
    }
    
    // Simple radial falloff - bright in center, fading out
    float radialFade = 1.0 - smoothstep(0.0, maxRadius, dist);
    
    // Simple pulsing glow
    float pulse = 0.8 + 0.2 * sin(u_Time * 15.0);
    
    // Effect intensity
    float effect = radialFade * u_shot_strength * pulse;
    
    // Bright warm color (yellow-orange-white)
    vec3 glowColor = mix(vec3(1.0, 0.8, 0.3), vec3(1.0, 1.0, 0.9), radialFade);
    
    // Strong additive blend for high visibility
    vec3 finalColor = original.rgb + glowColor * effect * 1.5;
    
    fragColor = vec4(finalColor, original.a);
}
