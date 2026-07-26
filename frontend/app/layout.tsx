import type { Metadata } from "next"
import "./globals.css"
import { Toaster } from "sonner"

export const metadata: Metadata = {
  title: "Note Digger — AI 自动钢琴扒谱",
  description: "将任意音频自动转录为高质量钢琴五线谱",
  keywords: ["扒谱", "钢琴谱", "AI转录", "五线谱"],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased" suppressHydrationWarning>
      <body className="min-h-full">
        {children}
        <Toaster position="top-center" richColors />
      </body>
    </html>
  )
}
