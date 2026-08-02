import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'HomeHamster - 家庭管理助手',
  description: '智能家庭账目管理与物品仓储管理 Agent',
  icons: {
    icon: '/hamsters/logo.png',
    apple: '/hamsters/logo.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
