import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Calendar, Check, Clock, MapPin, User } from "lucide-react";

export interface BookingCardProps {
  businessName: string;
  clientName: string;
  service: string;
  timeSlot: string;
  price?: string;
  primaryColor: string;
  accentColor: string;
  triggerTimeSeconds: number;
}

export const BookingCard: React.FC<BookingCardProps> = ({
  businessName,
  clientName,
  service,
  timeSlot,
  price,
  primaryColor,
  accentColor,
  triggerTimeSeconds,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  if (currentTime < triggerTimeSeconds) return null;

  const animFrames = Math.max(0, frame - Math.round(triggerTimeSeconds * fps));
  const progress = spring({
    frame: animFrames,
    fps,
    config: { damping: 14, stiffness: 110, mass: 0.7 },
  });

  const scale = interpolate(progress, [0, 1], [0.85, 1]);
  const opacity = interpolate(progress, [0, 1], [0, 1]);

  return (
    <div
      style={{
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        backdropFilter: "blur(16px)",
        borderRadius: 20,
        padding: "18px 24px",
        border: `2px solid ${accentColor}`,
        boxShadow: `0 14px 40px rgba(0, 0, 0, 0.4), 0 0 20px ${accentColor}44`,
        transform: `scale(${scale})`,
        opacity,
        width: "100%",
        maxWidth: 720,
        margin: "0 auto",
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
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              backgroundColor: accentColor,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#0F172A",
            }}
          >
            <Check size={20} strokeWidth={3} />
          </div>
          <span
            style={{
              fontSize: 16,
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: accentColor,
            }}
          >
            Confirmed Booking
          </span>
        </div>
        {price && (
          <span
            style={{
              fontSize: 20,
              fontWeight: 800,
              color: "#FFFFFF",
              backgroundColor: "rgba(255, 255, 255, 0.1)",
              padding: "4px 12px",
              borderRadius: 8,
            }}
          >
            {price}
          </span>
        )}
      </div>

      <div style={{ fontSize: 24, fontWeight: 800, color: "#FFFFFF", marginBottom: 12 }}>
        {service}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 16, color: "#94A3B8" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Clock size={18} color="#38BDF8" />
          <span style={{ color: "#F1F5F9", fontWeight: 600 }}>{timeSlot}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <User size={18} color="#A855F7" />
          <span>Client: <strong style={{ color: "#F1F5F9" }}>{clientName}</strong></span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <MapPin size={18} color="#F43F5E" />
          <span>{businessName}</span>
        </div>
      </div>
    </div>
  );
};
