import React from "react";
import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Mic, Phone, Radio, Sparkles } from "lucide-react";

export interface TalkingAvatarProps {
  type: "agent" | "caller";
  name: string;
  role: string;
  isSpeaking: boolean;
  amplitude: number;
  primaryColor: string;
  accentColor: string;
  imageSrc?: string;
}

export const TalkingAvatar: React.FC<TalkingAvatarProps> = ({
  type,
  name,
  role,
  isSpeaking,
  amplitude,
  primaryColor,
  accentColor,
  imageSrc,
}) => {
  const frame = useCurrentFrame();

  // Natural organic breathing and head movement
  const idleBreathe = Math.sin(frame * 0.06) * 2;
  const speakNod = isSpeaking ? Math.sin(frame * 0.28) * 3.5 : 0;
  const speakTilt = isSpeaking ? Math.sin(frame * 0.16) * 1.2 : 0;
  const headScale = isSpeaking ? 1 + interpolate(amplitude, [0, 0.4], [0, 0.05], { extrapolateRight: "clamp" }) : 1;
  const speechCadence = isSpeaking ? Math.sin(frame * 0.85) * 0.4 + 0.6 : 0;
  const jawSpeechScaleY = isSpeaking ? 1 + interpolate(amplitude * speechCadence, [0, 0.4], [0, 0.04], { extrapolateRight: "clamp" }) : 1;
  const jawSpeechScaleX = isSpeaking ? 1 - interpolate(amplitude * speechCadence, [0, 0.4], [0, 0.02], { extrapolateRight: "clamp" }) : 1;

  // Natural eyelid blinking (every ~110 frames for 6 frames)
  const blinkCycle = frame % 110;
  const isBlinking = blinkCycle >= 104 && blinkCycle <= 109;
  const blinkScaleY = isBlinking
    ? interpolate(blinkCycle, [104, 106, 107, 109], [1, 0.1, 0.1, 1])
    : 1;
  const mouthOpen = isSpeaking
    ? interpolate(amplitude * speechCadence, [0, 0.35], [0, 14], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;
  const mouthWidth = isSpeaking
    ? interpolate(amplitude * speechCadence, [0, 0.35], [26, 38], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 24;

  // Default avatar images
  const defaultImg =
    type === "agent"
      ? staticFile("avatars/ai_avatar.jpg")
      : staticFile("avatars/client_avatar.jpg");
  const finalImage = imageSrc || defaultImg;

  // Concentric audio pulse rings when speaking
  const pulse1 = isSpeaking ? (frame % 30) / 30 : 0;
  const pulse2 = isSpeaking ? ((frame + 15) % 30) / 30 : 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 24,
        position: "relative",
      }}
    >
      {/* ======================================================== */}
      {/* AVATAR PORTRAIT CONTAINER WITH REACTIVE MOTION            */}
      {/* ======================================================== */}
      <div
        style={{
          position: "relative",
          width: 165,
          height: 165,
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Concentric Speaking Shockwaves */}
        {isSpeaking && (
          <>
            <div
              style={{
                position: "absolute",
                width: 165,
                height: 165,
                borderRadius: "50%",
                border: `2px solid ${primaryColor}`,
                transform: `scale(${1 + pulse1 * 0.45})`,
                opacity: (1 - pulse1) * 0.7,
                pointerEvents: "none",
              }}
            />
            <div
              style={{
                position: "absolute",
                width: 165,
                height: 165,
                borderRadius: "50%",
                border: `2px solid ${primaryColor}`,
                transform: `scale(${1 + pulse2 * 0.45})`,
                opacity: (1 - pulse2) * 0.7,
                pointerEvents: "none",
              }}
            />
          </>
        )}

        {/* Outer Glowing Border Ring */}
        <div
          style={{
            position: "absolute",
            inset: -4,
            borderRadius: "50%",
            background: isSpeaking
              ? `conic-gradient(from ${frame * 4}deg, ${primaryColor}, ${accentColor}, ${primaryColor})`
              : "rgba(255, 255, 255, 0.12)",
            boxShadow: isSpeaking ? `0 0 30px ${primaryColor}88` : "none",
            transition: "box-shadow 0.2s ease",
          }}
        />

        {/* Head Motion Frame (Breathing + Nodding + Tilt + Micro Jaw Expansion) */}
        <div
          style={{
            position: "relative",
            width: 156,
            height: 156,
            borderRadius: "50%",
            overflow: "hidden",
            backgroundColor: "#0F172A",
            transform: `translateY(${idleBreathe + speakNod}px) rotate(${speakTilt}deg) scale(${headScale}) scale(${jawSpeechScaleX}, ${jawSpeechScaleY})`,
            boxShadow: "inset 0 0 25px rgba(0, 0, 0, 0.8)",
          }}
        >
          {/* Photorealistic Portrait */}
          <Img
            src={finalImage}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: isBlinking ? `scaleY(${blinkScaleY})` : "none",
              transformOrigin: "center 38%",
              filter: isSpeaking ? "brightness(1.04) contrast(1.02)" : "brightness(0.82) contrast(0.95)",
              transition: "filter 0.15s ease",
            }}
          />

          {/* Glowing Speech Energy Halo inside portrait when speaking */}
          {isSpeaking && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                borderRadius: "50%",
                background: `radial-gradient(circle at ${type === "agent" ? "48% 50%" : "46% 48%"}, ${primaryColor}33 0%, transparent 60%)`,
                opacity: interpolate(amplitude * speechCadence, [0, 0.3], [0.2, 0.85]),
                mixBlendMode: "screen",
                pointerEvents: "none",
                zIndex: 4,
              }}
            />
          )}

          {/* Glowing Headset Mic LED for AI Agent */}
          {type === "agent" && (
            <div
              style={{
                position: "absolute",
                top: "43%",
                right: "27%",
                width: 7,
                height: 7,
                borderRadius: "50%",
                backgroundColor: isSpeaking ? "#38BDF8" : "rgba(56, 189, 248, 0.3)",
                boxShadow: isSpeaking
                  ? "0 0 10px #38BDF8, 0 0 18px #38BDF8"
                  : "none",
                zIndex: 6,
              }}
            />
          )}

          {/* Glassmorphic Ambient Rim Overlay */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              background: `linear-gradient(135deg, ${primaryColor}22 0%, transparent 60%)`,
              pointerEvents: "none",
            }}
          />
        </div>

        {/* Live Audio Status Badge */}
        <div
          style={{
            position: "absolute",
            bottom: -2,
            right: -2,
            width: 32,
            height: 32,
            borderRadius: "50%",
            backgroundColor: isSpeaking ? primaryColor : "rgba(30, 41, 59, 0.9)",
            border: "2.5px solid #0B0F19",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: isSpeaking ? `0 0 12px ${primaryColor}` : "none",
            zIndex: 10,
          }}
        >
          {type === "agent" ? (
            <Sparkles size={16} color="#FFFFFF" />
          ) : (
            <Phone size={15} color="#FFFFFF" />
          )}
        </div>
      </div>

      {/* ======================================================== */}
      {/* AVATAR IDENTITY & LIVE EQUALIZER BARS                     */}
      {/* ======================================================== */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div
              style={{
                fontSize: 22,
                fontWeight: 900,
                color: "#FFFFFF",
                letterSpacing: "-0.01em",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span>{name}</span>
              {type === "agent" && (
                <span
                  style={{
                    fontSize: 11,
                    backgroundColor: "rgba(56, 189, 248, 0.2)",
                    color: "#38BDF8",
                    padding: "2px 8px",
                    borderRadius: 10,
                    fontWeight: 800,
                    border: "1px solid rgba(56, 189, 248, 0.4)",
                  }}
                >
                  AI BOT
                </span>
              )}
            </div>
            <div
              style={{
                fontSize: 14,
                color: isSpeaking ? "#E2E8F0" : "rgba(148, 163, 184, 0.8)",
                fontWeight: 600,
              }}
            >
              {role}
            </div>
          </div>

          {/* Mini Live Audio Equalizer Bars */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              gap: 3,
              height: 24,
              padding: "4px 8px",
              backgroundColor: "rgba(0, 0, 0, 0.35)",
              borderRadius: 8,
              border: `1px solid ${isSpeaking ? primaryColor + "55" : "rgba(255, 255, 255, 0.08)"}`,
            }}
          >
            {[0.4, 0.9, 0.6, 1.0, 0.5].map((multiplier, i) => {
              const barHeight = isSpeaking
                ? Math.max(4, Math.min(20, amplitude * 36 * multiplier + Math.sin(frame * 0.4 + i) * 3))
                : 3;
              return (
                <div
                  key={i}
                  style={{
                    width: 3.5,
                    height: barHeight,
                    backgroundColor: isSpeaking ? primaryColor : "rgba(148, 163, 184, 0.4)",
                    borderRadius: 2,
                    transition: "height 0.06s ease",
                  }}
                />
              );
            })}
          </div>
        </div>

        {/* Speaking Status Pill */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
            fontWeight: 800,
            color: isSpeaking ? primaryColor : "rgba(148, 163, 184, 0.6)",
            letterSpacing: "0.06em",
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              backgroundColor: isSpeaking ? primaryColor : "rgba(148, 163, 184, 0.3)",
              boxShadow: isSpeaking ? `0 0 8px ${primaryColor}` : "none",
            }}
          />
          <span>{isSpeaking ? "ACTIVE VOICE STREAM" : "STANDBY / LISTENING"}</span>
        </div>
      </div>
    </div>
  );
};
