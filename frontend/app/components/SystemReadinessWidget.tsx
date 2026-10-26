"use client";

import React, { useEffect, useState, useSyncExternalStore } from "react";

interface HealthState {
  is_live: boolean;
  is_ready: boolean;
  postgres: string;
  redis: string;
  checked_at: string;
}

const emptySubscribe = () => () => {};
const getClientSnapshot = () => true;
const getServerSnapshot = () => false;

export const SystemReadinessWidget: React.FC = () => {
  const [health, setHealth] = useState<HealthState>({
    is_live: false,
    is_ready: false,
    postgres: "checking",
    redis: "checking",
    checked_at: "",
  });

  const hasMounted = useSyncExternalStore(emptySubscribe, getClientSnapshot, getServerSnapshot);
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    let active = true;
    const checkStatus = async () => {
      try {
        const [liveRes, readyRes] = await Promise.all([
          fetch(`${apiBase}/health/live`).catch(() => null),
          fetch(`${apiBase}/health/ready`).catch(() => null),
        ]);

        if (!active) return;

        const isLive = liveRes ? liveRes.ok : false;
        let isReady = false;
        let pgStatus = "unreachable";
        let redisStatus = "unreachable";

        if (readyRes && readyRes.ok) {
          isReady = true;
          try {
            const readyData = await readyRes.json();
            pgStatus = readyData.dependencies?.postgres || "healthy";
            redisStatus = readyData.dependencies?.redis || "healthy";
          } catch {
            pgStatus = "healthy";
            redisStatus = "healthy";
          }
        } else if (isLive) {
          pgStatus = "degraded";
          redisStatus = "degraded";
        }

        setHealth({
          is_live: isLive,
          is_ready: isReady,
          postgres: pgStatus,
          redis: redisStatus,
          checked_at: new Date().toLocaleTimeString(),
        });
      } catch {
        if (!active) return;
        setHealth({
          is_live: false,
          is_ready: false,
          postgres: "down",
          redis: "down",
          checked_at: new Date().toLocaleTimeString(),
        });
      }
    };

    void checkStatus();
    const interval = setInterval(() => {
      void checkStatus();
    }, 10000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [apiBase]);

  const components = [
    {
      name: "FastAPI Runtime Gateway",
      status: health.is_live ? "OPERATIONAL" : "DOWN",
      healthy: health.is_live,
      desc: "In-line request proxy & correlation tracing",
    },
    {
      name: "PostgreSQL Database Engine",
      status: health.postgres.toUpperCase(),
      healthy: health.postgres === "healthy",
      desc: "Multi-tenant persistence & schema migrations",
    },
    {
      name: "Redis Budget & Rate Governor",
      status: health.redis.toUpperCase(),
      healthy: health.redis === "healthy",
      desc: "Atomic concurrency locks & token spend quotas",
    },
    {
      name: "Deterministic Policy Boundary",
      status: health.is_live ? "ACTIVE" : "OFFLINE",
      healthy: health.is_live,
      desc: "Pre-execution security rules & token issuance",
    },
  ];

  return (
    <section id="system-readiness-section" className="glass-panel" style={{ padding: "18px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
        <h2 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)" }}>
          Platform Infrastructure Health &amp; Readiness Probes
        </h2>
        <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          Probe Sync: {hasMounted && health.checked_at ? health.checked_at : "Checking..."}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px" }}>
        {components.map((comp) => (
          <div
            key={comp.name}
            style={{
              background: "#ffffff",
              border: "1px solid #eef2f6",
              borderRadius: "12px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "6px",
              boxShadow: "0 1px 3px rgba(15, 23, 42, 0.02)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px" }}>
              <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-primary)" }}>
                {comp.name}
              </span>
              <span className={`badge ${comp.healthy ? "badge-allow" : "badge-block"}`} style={{ fontSize: "0.6875rem" }}>
                {comp.status}
              </span>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", lineHeight: "1.4" }}>
              {comp.desc}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
