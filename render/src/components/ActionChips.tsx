import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Calendar, CheckCircle2, Clock, MessageSquare, PhoneForwarded, UserCheck } from "lucide-react";

export interface ActionEvent {
  turn_index: number;
  time_seconds: number;
  type: "tool_call" | "booking_card" | "owner_notification" | "escalation";
  text: string;
}

export interface ActionChipsProps {
  events: ActionEvent[];
  primaryColor: string;
  accentColor: string;
}

const getIcon = (type: string, text: string) => {
  if (text.toLowerCase().includes("calendar") || text.toLowerCase().includes("slot")) {
    return <Calendar size={22} color="#10B981" />;
  }
  if (text.toLowerCase().includes("book") || text.toLowerCase().includes("confirm")) {
    return <CheckCircle2 size={22} color="#38BDF8" />;
  }
  if (text.toLowerCase().includes("time") || text.toLowerCase().includes("hour")) {
    return <Clock size={22} color="#FBBF24" />;
  }
  if (type === "escalation") {
    return <PhoneForwarded size={22} color="#F43F5E" />;
  }
  return <UserCheck size={22} color="#A855F7" />;
};

export const ActionChips: React.FC<ActionChipsProps> = ({
  events,
  primaryColor,
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Show events that have already triggered, but keep at most the last 3 visible
  const triggeredEvents = events
    .filter((e) => currentTime >= e.time_seconds)
    .slice(-3);

  if (triggeredEvents.length === 0) return null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        width: "100%",
        maxWidth: 720,
        margin: "0 auto",
      }}
    >
      {triggeredEvents.map((evt, idx) => {
        const eventAgeFrames = Math.max(0, frame - Math.round(evt.time_seconds * fps));
        const slideProgress = spring({
          frame: eventAgeFrames,
          fps,
          config: { damping: 14, stiffness: 120, mass: 0.6 },
        });

        const translateY = interpolate(slideProgress, [0, 1], [30, 0]);
        const opacity = interpolate(slideProgress, [0, 1], [0, 1]);

        return (
          <div
            key={`${evt.time_seconds}-${idx}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              backgroundColor: "rgba(15, 23, 42, 0.88)",
              backdropFilter: "blur(12px)",
              padding: "12px 20px",
              borderRadius: 30,
              border: `1.5px solid ${accentColor}55`,
              boxShadow: "0 8px 24px rgba(0, 0, 0, 0.35)",
              transform: `translateY(${translateY}px)`,
              opacity,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 38,
                height: 38,
                borderRadius: "50%",
                backgroundColor: "rgba(255, 255, 255, 0.08)",
              }}
            >
              {getIcon(evt.type, evt.text)}
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: "#94A3B8",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                }}
              >
                AI Agent Action
              </span>
              <span
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: "#F8FAFC",
                }}
              >
                {evt.text}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
