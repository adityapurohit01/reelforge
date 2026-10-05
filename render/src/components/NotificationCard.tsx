import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Bell, CheckCheck } from "lucide-react";

export interface OwnerNotificationData {
  summary: string;
  customer_name: string;
  time_or_slot?: string;
  service_requested?: string;
  next_step?: string;
}

export interface NotificationCardProps {
  notification: OwnerNotificationData;
  triggerTimeSeconds: number;
  businessName: string;
  accentColor: string;
}

export const NotificationCard: React.FC<NotificationCardProps> = ({
  notification,
  triggerTimeSeconds,
  businessName,
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  if (currentTime < triggerTimeSeconds) return null;

  const animFrames = Math.max(0, frame - Math.round(triggerTimeSeconds * fps));
  const slideProgress = spring({
    frame: animFrames,
    fps,
    config: { damping: 16, stiffness: 100, mass: 0.8 },
  });

  const translateY = interpolate(slideProgress, [0, 1], [-120, 0]);
  const opacity = interpolate(slideProgress, [0, 1], [0, 1]);

  return (
    <div
      style={{
        position: "absolute",
        top: 140, // Below top safe area
        left: "50%",
        transform: `translateX(-50%) translateY(${translateY}px)`,
        opacity,
        width: "90%",
        maxWidth: 960,
        backgroundColor: "rgba(18, 24, 38, 0.95)",
        backdropFilter: "blur(20px)",
        borderRadius: 24,
        padding: "20px 26px",
        border: "1.5px solid rgba(255, 255, 255, 0.15)",
        boxShadow: "0 20px 50px rgba(0, 0, 0, 0.5), 0 0 30px rgba(16, 185, 129, 0.2)",
        zIndex: 50,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: "50%",
              backgroundColor: "#10B981",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Bell size={20} color="#FFFFFF" />
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#FFFFFF" }}>
              {businessName} Receptionist
            </div>
            <div style={{ fontSize: 14, color: "#94A3B8" }}>Instant Call Summary</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#10B981", fontSize: 14 }}>
          <span>Just now</span>
          <CheckCheck size={18} />
        </div>
      </div>

      <div
        style={{
          fontSize: 22,
          fontWeight: 600,
          color: "#F1F5F9",
          lineHeight: 1.4,
          marginBottom: 10,
        }}
      >
        {notification.summary}
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          marginTop: 8,
          fontSize: 15,
        }}
      >
        {notification.customer_name && (
          <span
            style={{
              backgroundColor: "rgba(255, 255, 255, 0.08)",
              padding: "6px 12px",
              borderRadius: 8,
              color: "#E2E8F0",
            }}
          >
            👤 <strong>Caller:</strong> {notification.customer_name}
          </span>
        )}
        {notification.time_or_slot && (
          <span
            style={{
              backgroundColor: "rgba(16, 185, 129, 0.15)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              padding: "6px 12px",
              borderRadius: 8,
              color: "#34D399",
            }}
          >
            📅 <strong>Slot:</strong> {notification.time_or_slot}
          </span>
        )}
        {notification.service_requested && (
          <span
            style={{
              backgroundColor: "rgba(56, 189, 248, 0.15)",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              padding: "6px 12px",
              borderRadius: 8,
              color: "#38BDF8",
            }}
          >
            🏷️ <strong>Service:</strong> {notification.service_requested}
          </span>
        )}
      </div>
    </div>
  );
};
