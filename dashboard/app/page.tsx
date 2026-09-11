"use client";

import React, { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { StatCard } from "./components/StatCard";
import { ApprovalQueueWidget } from "./components/ApprovalQueueWidget";
import { LiveInterceptionFeed } from "./components/LiveInterceptionFeed";
import { SystemReadinessWidget } from "./components/SystemReadinessWidget";

export default function Home() {
  const [activeTab, setActiveTab] = useState("overview");
  const [isKilled, setIsKilled] = useState(false);

  const toggleKillSwitch = () => {
    setIsKilled(!isKilled);
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-primary)" }}>
      {/* 1. Left Fixed Navigation Sidebar */}
      <Sidebar activeTab={activeTab} onSelectTab={setActiveTab} />

      {/* 2. Main Content Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Header onTriggerKillSwitch={toggleKillSwitch} isKilled={isKilled} />

        <main id="main-content" style={{ padding: "32px", display: "flex", flexDirection: "column", gap: "28px" }}>
          {/* Emergency Kill Switch Banner if Active */}
          {isKilled && (
            <div
              id="banner-kill-switch-active"
              className="glass-panel"
              style={{
                padding: "16px 20px",
                background: "rgba(244, 63, 94, 0.2)",
                border: "1px solid #F43F5E",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <span style={{ fontSize: "1.5rem" }}>⚠️</span>
                <div>
                  <div style={{ fontWeight: 700, color: "#FFF", fontSize: "0.95rem" }}>
                    GLOBAL KILL SWITCH ACTIVATED — ALL AGENT SESSIONS SUSPENDED
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#FECDD3" }}>
                    All outbound tool dispatches are frozen with verdict SUSPEND. No new actions can be submitted.
                  </div>
                </div>
              </div>
              <button className="btn btn-ghost" onClick={toggleKillSwitch} style={{ fontSize: "0.8rem", color: "#FFF" }}>
                Deactivate Kill Switch
              </button>
            </div>
          )}

          {/* Section: Overview Metrics */}
          <section id="metrics-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
            <StatCard
              id="stat-actions-mediated"
              title="Actions Mediated (24h)"
              value="142,890"
              trend="+14.2%"
              subtitle="1,240 actions/sec peak throughput"
              icon="⚡"
              accentColor="#00F0FF"
            />
            <StatCard
              id="stat-decisions-allow"
              title="ALLOW Rate"
              value="84.2%"
              trend="+0.8%"
              subtitle="Passed all deterministic constraints"
              icon="✅"
              accentColor="#10B981"
            />
            <StatCard
              id="stat-decisions-blocked"
              title="Threats Blocked"
              value="12,410"
              trend="-2.1%"
              subtitle="9.1% of all evaluated invocations"
              icon="🛡️"
              accentColor="#F43F5E"
            />
            <StatCard
              id="stat-p95-latency"
              title="P95 Decision Latency"
              value="4.2 ms"
              trend="-0.6ms"
              subtitle="Target < 15ms (Exceeding SLA)"
              icon="⏱️"
              accentColor="#38BDF8"
            />
            <StatCard
              id="stat-active-sessions"
              title="Active Agent Sessions"
              value={isKilled ? "0" : "18"}
              subtitle={isKilled ? "All sessions suspended" : "Scoped across 3 projects"}
              icon="🤖"
              accentColor="#A855F7"
            />
          </section>

          {/* Section: Cryptographic Human Approvals Queue */}
          <ApprovalQueueWidget />

          {/* Section: Live In-Line Interception Feed */}
          <LiveInterceptionFeed />

          {/* Section: Infrastructure Health & Readiness */}
          <SystemReadinessWidget />
        </main>
      </div>
    </div>
  );
}
