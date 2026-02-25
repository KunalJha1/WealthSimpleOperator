/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./lib/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"]
      },
      colors: {
        ws: {
          green: "#1e8f63",
          greenSoft: "#f2f7f5",
          border: "#e5e5e5",
          muted: "#737373",
          background: "#fafafa",
          ink: "#171717"
        }
      },
      borderRadius: {
        xl: "0.9rem"
      }
    }
  },
  plugins: []
};

