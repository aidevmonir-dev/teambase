import type { NextConfig } from "next";

// Production builds are a static export served by Django (one origin for the app and /api).
// In development, `next dev` proxies /api to the Django dev server instead.
const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  trailingSlash: true,
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  ...(isDev
    ? {
        async rewrites() {
          return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*/" }];
        },
      }
    : { output: "export" as const }),
};

export default nextConfig;
