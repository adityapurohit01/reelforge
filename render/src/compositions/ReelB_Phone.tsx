import React from "react";
import { AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Waveform } from "../components/Waveform";
import { Captions } from "../components/Captions";
import { ActionChips } from "../components/ActionChips";
import { NotificationCard } from "../components/NotificationCard";
import { HookCard } from "../components/HookCard";
import { EndCard } from "../components/EndCard";
import { ReelProps } from "./ReelA_Split";
import { Mic, PhoneOff, Volume2, ShieldCheck, Sparkles } from "lucide-react";

export const ReelB_Phone: React.FC<ReelProps> = ({
  business,
  hook_text,
  audio_url,
  total_duration_seconds,
  palette,
  caption_style,
  words,
  events,
  amplitude_envelope,
  owner_notification,
  product,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  const currentWord = words.find((w) => currentTime >= w.start && currentTime <= w.end);
  const currentSpeaker = currentWord ? currentWord.speaker : "none";

  const minutes = Math.floor(currentTime / 60);
  const seconds = Math.floor(currentTime % 60);
  const timeFormatted = `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;

  const notificationTrigger = total_duration_seconds * 0.7;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: palette.background,
        color: palette.text,
        fontFamily: "'Outfit', sans-serif",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "70px 48px",
        overflow: "hidden",
      }}
    >
      {audio_url && <Audio src={audio_url.startsWith("http") ? audio_url : staticFile(audio_url)} />}

      {/* TOP: Phone status & Business Identity */}
      <div
        style={{
          width: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          marginTop: 20,
        }}
      >
        {/* Dynamic Island / Pill */}
        <div
          style={{
            backgroundColor: "#000000",
            padding: "8px 24px",
            borderRadius: 30,
            display: "flex",
            alignItems: "center",
            gap: 12,
            border: "1px solid rgba(255, 255, 255, 0.15)",
            marginBottom: 36,
          }}
        >
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: "50%",
              backgroundColor: "#10B981",
              boxShadow: "0 0 10px #10B981",
            }}
          />
          <span style={{ fontSize: 16, fontWeight: 700, color: "#FFFFFF", letterSpacing: "0.05em" }}>
            AI VOICE CALL • {timeFormatted}
          </span>
        </div>

        {/* Business Avatar / Logo */}
        <div
          style={{
            width: 130,
            height: 130,
            borderRadius: "50%",
            backgroundColor: palette.surface,
            border: `3px solid ${palette.primary}`,
            boxShadow: `0 0 40px ${palette.primary}55`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 52,
            fontWeight: 900,
            color: palette.primary,
            marginBottom: 20,
          }}
        >
          {business.name.charAt(0)}
        </div>

        <h1 style={{ fontSize: 50, fontWeight: 900, margin: "0 0 6px 0", color: "#FFFFFF", textAlign: "center" }}>
          {business.name}
        </h1>
        <div style={{ fontSize: 24, color: palette.textSecondary, fontWeight: 600 }}>
          {business.vertical} • {business.city}
        </div>
      </div>

      {/* CENTER: Audio Waveform */}
      <div style={{ width: "100%", margin: "20px 0" }}>
        <Waveform
          envelope={amplitude_envelope}
          currentSpeaker={currentSpeaker}
          agentColor={palette.agentWaveform}
          callerColor={palette.callerWaveform}
          barCount={42}
        />
      </div>

      {/* ACTIONS RAIL */}
      <div style={{ width: "100%", zIndex: 10 }}>
        <ActionChips
          events={events}
          primaryColor={palette.primary}
          accentColor={palette.accent}
        />
      </div>

      {/* BOTTOM: Captions & Call Controls */}
      <div
        style={{
          width: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 20,
        }}
      >
        <Captions
          words={words}
          styleType={caption_style}
          primaryColor={palette.primary}
          accentColor={palette.accent}
          textColor={palette.text}
        />

        {/* Phone UI Control Buttons */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 36,
            marginTop: 10,
          }}
        >
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: "50%",
              backgroundColor: "rgba(255, 255, 255, 0.1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#FFFFFF",
            }}
          >
            <Mic size={28} />
          </div>
          <div
            style={{
              width: 76,
              height: 76,
              borderRadius: "50%",
              backgroundColor: "#EF4444",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#FFFFFF",
              boxShadow: "0 8px 25px rgba(239, 68, 68, 0.4)",
            }}
          >
            <PhoneOff size={34} />
          </div>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: "50%",
              backgroundColor: "rgba(255, 255, 255, 0.1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#FFFFFF",
            }}
          >
            <Volume2 size={28} />
          </div>
        </div>

        <div
          style={{
            fontSize: 16,
            fontWeight: 600,
            color: "rgba(255, 255, 255, 0.45)",
            marginTop: 8,
          }}
        >
          Simulated call • Fictional business
        </div>
      </div>

      <NotificationCard
        notification={owner_notification}
        triggerTimeSeconds={notificationTrigger}
        businessName={business.name}
        accentColor={palette.accent}
      />

      <HookCard
        hookText={hook_text}
        businessName={business.name}
        vertical={business.vertical}
        primaryColor={palette.primary}
        accentColor={palette.accent}
      />

      <EndCard
        productName={product.name}
        tagline={product.tagline}
        ctaUrl={product.cta_url}
        ctaHandle={product.cta_handle}
        primaryColor={palette.primary}
        accentColor={palette.accent}
        totalDurationFrames={Math.round(total_duration_seconds * fps)}
      />
    </AbsoluteFill>
  );
};
