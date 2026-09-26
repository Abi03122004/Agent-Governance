import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
    variable: "--font-geist-sans",
    subsets: ["latin"],
});

const geistMono = Geist_Mono({
    variable: "--font-geist-mono",
    subsets: ["latin"],
});

export const metadata = {
    title: "Agent Governance",
    description: "Runtime security and monitoring for AI agents",
};

export default function RootLayout({ children }) {
    return (
        <html
            lang="en"
            className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
        >
            <body className="min-h-full flex bg-black text-white">
                <aside className="w-64 border-r border-gray-800 bg-gray-950 p-4">
                    <p className="mb-8 text-lg font-bold tracking-wide text-blue-400">AGENT GOVERNANCE</p>
                    <nav className="flex flex-col gap-2 text-sm text-gray-300">
                        <a className="rounded px-4 py-2 hover:bg-gray-800 hover:text-white" href="/agents">Agents & Activity</a>
                        <a className="rounded px-4 py-2 hover:bg-gray-800 hover:text-white" href="/organizations">Organizations</a>
                        <a className="rounded px-4 py-2 hover:bg-gray-800 hover:text-white" href="/projects">Projects</a>
                        <a className="rounded px-4 py-2 hover:bg-gray-800 hover:text-white" href="/sessions">Sessions</a>
                    </nav>
                </aside>
                <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
            </body>
        </html>
    );
}
