import React from "react";
import { AbsoluteFill, Audio, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Waveform } from "../components/Waveform";
import { Captions, WordTimestamp } from "../components/Captions";
import { ActionChips, ActionEvent } from "../components/ActionChips";
import { NotificationCard, OwnerNotificationData } from "../components/NotificationCard";
import { HookCard } from "../components/HookCard";
import { EndCard } from "../components/EndCard";
import { TalkingAvatar } from "../components/TalkingAvatar";
import { ColorPalette } from "../themes/palettes";
import { Bot, User, PhoneCall, Sparkles, Radio, CheckCircle2 } from "lucide-react";

export interface ReelProps {
  business: {
    name: string;
    vertical: string;
    city: string;
    owner_name: string;
  };
  hook_text: string;
  audio_url: string;
  total_duration_seconds: number;
  palette: ColorPalette;
  caption_style: "word-highlight" | "karaoke" | "boxed";
  words: WordTimestamp[];
  events: ActionEvent[];
  amplitude_envelope: number[];
  owner_notification: OwnerNotificationData;
  product: {
    name: string;
    tagline: string;
    cta_url: string;
    cta_handle: string;
  };
}

export const ReelA_Split: React.FC<ReelProps> = ({
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

  // Determine current active speaker
  const currentWord = words.find((w) => currentTime >= w.start && currentTime <= w.end);
  const currentSpeaker = currentWord ? currentWord.speaker : "none";
  const isAgentSpeaking = currentSpeaker === "agent";
  const isCallerSpeaking = currentSpeaker === "caller";

  // Current amplitude for pulsation
  const amp = amplitude_envelope[frame] || 0.05;

  // Pulse scales for avatars
  const agentPulse = isAgentSpeaking ? 1 + amp * 0.18 : 1;
  const callerPulse = isCallerSpeaking ? 1 + amp * 0.18 : 1;

  // Format call timer mm:ss
  const minutes = Math.floor(currentTime / 60);
  const seconds = Math.floor(currentTime % 60);
  const formattedTimer = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  // Filter words belonging to current speaker for focused in-panel display
  const agentWords = words.filter((w) => w.speaker === "agent");
  const callerWords = words.filter((w) => w.speaker === "caller");

  const notificationTrigger = total_duration_seconds * 0.72;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: palette.background,
        color: palette.text,
        fontFamily: "'Inter', sans-serif",
        display: "flex",
        flexDirection: "column",
        padding: "60px 36px 40px 36px",
        overflow: "hidden",
        justifyContent: "space-between",
      }}
    >
      {/* Audio Playback */}
      {audio_url && <Audio src={audio_url.startsWith("http") ? audio_url : staticFile(audio_url)} />}

      {/* TOP HEADER: Business Branding Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "16px 24px",
          backgroundColor: "rgba(255, 255, 255, 0.04)",
          borderRadius: 20,
          border: `1px solid ${palette.border}`,
          marginBottom: 16,
          zIndex: 10,
        }}
      >
        <div>
          <div style={{ fontSize: 28, fontWeight: 900, color: "#FFFFFF" }}>{business.name}</div>
          <div style={{ fontSize: 16, color: palette.textSecondary, fontWeight: 600 }}>
            {business.vertical} • {business.city}
          </div>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            backgroundColor: "rgba(16, 185, 129, 0.15)",
            padding: "8px 16px",
            borderRadius: 16,
            color: "#10B981",
            fontWeight: 700,
            fontSize: 16,
          }}
        >
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              backgroundColor: "#10B981",
              boxShadow: "0 0 10px #10B981",
            }}
          />
          <span>LIVE • {formattedTimer}</span>
        </div>
      </div>

      {/* ======================================================== */}
      {/* TOP HALF: ROBOT / AI VOICE RECEPTIONIST                  */}
      {/* ======================================================== */}
      <div
        style={{
          flex: "1 1 45%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          position: "relative",
          backgroundColor: isAgentSpeaking ? palette.surface : "rgba(15, 23, 42, 0.55)",
          borderRadius: 32,
          border: isAgentSpeaking ? `2.5px solid ${palette.primary}` : `1.5px solid ${palette.border}`,
          padding: "24px 28px",
          boxShadow: isAgentSpeaking ? `0 0 40px ${palette.primary}44` : "none",
          transition: "border 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease",
          opacity: isCallerSpeaking ? 0.72 : 1,
        }}
      >
        {/* Top Badges */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              backgroundColor: isAgentSpeaking ? palette.primary : "rgba(255, 255, 255, 0.1)",
              color: "#FFFFFF",
              padding: "8px 18px",
              borderRadius: 20,
              fontSize: 16,
              fontWeight: 800,
              letterSpacing: "0.04em",
            }}
          >
            <Bot size={22} />
            <span>AI RECEPTIONIST</span>
          </div>

          <div
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: isAgentSpeaking ? "#10B981" : palette.textSecondary,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {isAgentSpeaking ? (
              <>
                <Radio size={16} />
                <span>SPEAKING</span>
              </>
            ) : (
              <span>LISTENING...</span>
            )}
          </div>
        </div>

        {/* Central Photorealistic AI Talking Avatar */}
        <div style={{ margin: "14px 0" }}>
          <TalkingAvatar
            type="agent"
            name="Anya"
            role={`AI Receptionist • ${business.name}`}
            isSpeaking={isAgentSpeaking}
            amplitude={amp}
            primaryColor={palette.primary}
            accentColor={palette.accent}
            imageSrc={staticFile("avatars/ai_avatar.jpg")}
          />
        </div>

        {/* AI Equalizer Waveform */}
        <div style={{ margin: "6px 0" }}>
          <Waveform
            envelope={amplitude_envelope}
            currentSpeaker={isAgentSpeaking ? "agent" : "none"}
            agentColor={palette.agentWaveform}
            callerColor={palette.callerWaveform}
            barCount={36}
          />
        </div>

        {/* Subtitle / Speech Display for Robot */}
        <div
          style={{
            minHeight: 80,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            backgroundColor: "rgba(0, 0, 0, 0.3)",
            borderRadius: 20,
            padding: "12px 18px",
          }}
        >
          {isAgentSpeaking ? (
            <Captions
              words={agentWords}
              styleType={caption_style}
              primaryColor={palette.primary}
              accentColor={palette.accent}
              textColor="#FFFFFF"
            />
          ) : (
            <span style={{ fontSize: 18, color: palette.textSecondary, fontStyle: "italic" }}>
              Waiting for customer...
            </span>
          )}
        </div>
      </div>

      {/* ======================================================== */}
      {/* CENTER DIVIDER & ACTION CHIPS RAIL                       */}
      {/* ======================================================== */}
      <div style={{ margin: "14px 0", zIndex: 10 }}>
        <ActionChips events={events} primaryColor={palette.primary} accentColor={palette.accent} />
      </div>

      {/* ======================================================== */}
      {/* BOTTOM HALF: CLIENT / CUSTOMER                           */}
      {/* ======================================================== */}
      <div
        style={{
          flex: "1 1 45%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          position: "relative",
          backgroundColor: isCallerSpeaking ? palette.surface : "rgba(15, 23, 42, 0.55)",
          borderRadius: 32,
          border: isCallerSpeaking ? `2.5px solid ${palette.callerWaveform}` : `1.5px solid ${palette.border}`,
          padding: "24px 28px",
          boxShadow: isCallerSpeaking ? `0 0 40px ${palette.callerWaveform}44` : "none",
          transition: "border 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease",
          opacity: isAgentSpeaking ? 0.72 : 1,
        }}
      >
        {/* Bottom Badges */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              backgroundColor: isCallerSpeaking ? palette.callerWaveform : "rgba(255, 255, 255, 0.1)",
              color: "#FFFFFF",
              padding: "8px 18px",
              borderRadius: 20,
              fontSize: 16,
              fontWeight: 800,
              letterSpacing: "0.04em",
            }}
          >
            <User size={22} />
            <span>CLIENT / CALLER</span>
          </div>

          <div
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: isCallerSpeaking ? palette.callerWaveform : palette.textSecondary,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {isCallerSpeaking ? (
              <>
                <Radio size={16} />
                <span>SPEAKING</span>
              </>
            ) : (
              <span>LISTENING...</span>
            )}
          </div>
        </div>

        {/* Central Photorealistic Caller Talking Avatar */}
        <div style={{ margin: "14px 0" }}>
          <TalkingAvatar
            type="caller"
            name="Customer"
            role="Live Inbound Caller"
            isSpeaking={isCallerSpeaking}
            amplitude={amp}
            primaryColor={palette.callerWaveform}
            accentColor={palette.accent}
            imageSrc={staticFile("avatars/client_avatar.jpg")}
          />
        </div>

        {/* Caller Equalizer Waveform */}
        <div style={{ margin: "6px 0" }}>
          <Waveform
            envelope={amplitude_envelope}
            currentSpeaker={isCallerSpeaking ? "caller" : "none"}
            agentColor={palette.agentWaveform}
            callerColor={palette.callerWaveform}
            barCount={36}
          />
        </div>

        {/* Subtitle / Speech Display for Caller */}
        <div
          style={{
            minHeight: 80,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            backgroundColor: "rgba(0, 0, 0, 0.3)",
            borderRadius: 20,
            padding: "12px 18px",
          }}
        >
          {isCallerSpeaking ? (
            <Captions
              words={callerWords}
              styleType={caption_style}
              primaryColor={palette.callerWaveform}
              accentColor={palette.accent}
              textColor="#FFFFFF"
            />
          ) : (
            <span style={{ fontSize: 18, color: palette.textSecondary, fontStyle: "italic" }}>
              Listening to AI receptionist...
            </span>
          )}
        </div>
      </div>

      {/* Mandatory On-Screen Compliance Watermark */}
      <div
        style={{
          textAlign: "center",
          fontSize: 15,
          fontWeight: 600,
          color: "rgba(255, 255, 255, 0.4)",
          letterSpacing: "0.04em",
          marginTop: 10,
        }}
      >
        Simulated call • Fictional business
      </div>

      {/* Floating Owner WhatsApp/Telegram Notification Card */}
      <NotificationCard
        notification={owner_notification}
        triggerTimeSeconds={notificationTrigger}
        businessName={business.name}
        accentColor={palette.accent}
      />

      {/* Hook Card (first 2.5s) */}
      <HookCard
        hookText={hook_text}
        businessName={business.name}
        vertical={business.vertical}
        primaryColor={palette.primary}
        accentColor={palette.accent}
      />

      {/* End Card (last 2.6s) */}
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
