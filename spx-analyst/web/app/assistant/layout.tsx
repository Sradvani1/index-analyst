export default function AssistantLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <div className="flex min-h-[calc(100vh-4rem)] flex-col">{children}</div>;
}
