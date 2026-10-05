import React from "react";
import { AbsoluteFill, Audio, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Waveform } from "../components/Waveform";
import { Captions } from "../components/Captions";
import { ActionChips } from "../components/ActionChips";
import { NotificationCard } from "../components/NotificationCard";
import { HookCard } from "../components/HookCard";
import { EndCard } from "../components/EndCard";
import { ReelProps } from "./ReelA_Split";
import { Bot, User, MessageSquare } from "lucide-react";

export const ReelC_Chat: React.FC<ReelProps> = ({
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

  const notificationTrigger = total_duration_seconds * 0.7;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: palette.background,
        color: palette.text,
        fontFamily: "'Plus Jakarta Sans', sans-serif",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "70px 40px",
        overflow: "hidden",
      }}
    >
      {audio_url && <Audio src={audio_url.startsWith("http") ? audio_url : staticFile(audio_url)} />}

      {/* HEADER: Live AI Receptionist Session */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 28px",
          backgroundColor: palette.surface,
          borderRadius: 24,
          border: `1.5px solid ${palette.border}`,
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.3)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 50,
              height: 50,
              borderRadius: "50%",
              backgroundColor: palette.primary,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#FFFFFF",
            }}
          >
            <Bot size={26} />
          </div>
          <div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "#FFFFFF" }}>
              {business.name}
            </div>
            <div style={{ fontSize: 16, color: "#10B981", fontWeight: 700 }}>
              ● AI Voice Receptionist Active
            </div>
          </div>
        </div>

        <div
          style={{
            fontSize: 16,
            fontWeight: 700,
            color: palette.textSecondary,
            backgroundColor: "rgba(255, 255, 255, 0.08)",
            padding: "8px 16px",
            borderRadius: 16,
          }}
        >
          {business.vertical}
        </div>
      </div>

      {/* WAVEFORM BAR */}
      <div style={{ margin: "16px 0" }}>
        <Waveform
          envelope={amplitude_envelope}
          currentSpeaker={currentSpeaker}
          agentColor={palette.agentWaveform}
          callerColor={palette.callerWaveform}
          barCount={34}
        />
      </div>

      {/* ACTION CHIPS */}
      <div style={{ zIndex: 10 }}>
        <ActionChips
          events={events}
          primaryColor={palette.primary}
          accentColor={palette.accent}
        />
      </div>

      {/* CHAT/CAPTIONS CONTAINER */}
      <div
        style={{
          flex: "1 1 45%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          position: "relative",
          backgroundColor: "rgba(15, 23, 42, 0.5)",
          borderRadius: 30,
          border: "1px solid rgba(255, 255, 255, 0.08)",
          padding: 24,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 20,
            left: 28,
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 18,
            fontWeight: 700,
            color: currentSpeaker === "agent" ? palette.primary : palette.callerWaveform,
          }}
        >
          {currentSpeaker === "agent" ? <Bot size={20} /> : <User size={20} />}
          <span>{currentSpeaker === "agent" ? "Receptionist" : "Caller"} speaking...</span>
        </div>

        <Captions
          words={words}
          styleType={caption_style}
          primaryColor={palette.primary}
          accentColor={palette.accent}
          textColor={palette.text}
        />
      </div>

      {/* Safe Area Footer */}
      <div
        style={{
          textAlign: "center",
          fontSize: 16,
          fontWeight: 600,
          color: "rgba(255, 255, 255, 0.45)",
          marginTop: 12,
        }}
      >
        Simulated call • Fictional business
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
