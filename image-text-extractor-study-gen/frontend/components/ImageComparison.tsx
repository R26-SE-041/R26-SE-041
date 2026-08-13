"use client";

interface Props {
  originalB64: string;
  enhancedB64: string;
}

export default function ImageComparison({ originalB64, enhancedB64 }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Side-by-side or stacked container */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "1.5rem",
        }}
      >
        {/* Original */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <div
            style={{
              display: "inline-flex",
              alignSelf: "flex-start",
              borderRadius: "0.375rem",
              background: "rgba(255,255,255,0.08)",
              padding: "0.25rem 0.75rem",
              color: "rgba(255,255,255,0.8)",
              fontSize: "0.875rem",
              fontWeight: 500,
            }}
          >
            Original
          </div>
          <div
            style={{
              overflow: "hidden",
              borderRadius: "0.75rem",
              border: "1px solid rgba(255,255,255,0.1)",
              background: "rgba(0,0,0,0.2)",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`data:image/png;base64,${originalB64}`}
              alt="Original image"
              style={{
                width: "100%",
                height: "auto",
                maxHeight: "60vh",
                objectFit: "contain",
                display: "block",
              }}
            />
          </div>
        </div>

        {/* Enhanced */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <div
            style={{
              display: "inline-flex",
              alignSelf: "flex-start",
              borderRadius: "0.375rem",
              background: "rgba(139,92,246,0.2)",
              padding: "0.25rem 0.75rem",
              color: "#c4b5fd",
              fontSize: "0.875rem",
              fontWeight: 500,
            }}
          >
            Enhanced (4x)
          </div>
          <div
            style={{
              overflow: "hidden",
              borderRadius: "0.75rem",
              border: "1px solid rgba(139,92,246,0.3)",
              background: "rgba(0,0,0,0.2)",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`data:image/png;base64,${enhancedB64}`}
              alt="Enhanced image"
              style={{
                width: "100%",
                height: "auto",
                maxHeight: "60vh",
                objectFit: "contain",
                display: "block",
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
