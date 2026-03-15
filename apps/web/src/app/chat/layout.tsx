"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { ConversationList } from "@/components/sidebar/conversation-list";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading, user, logout } = useAuth();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden w-[280px] shrink-0 border-r bg-muted/30 md:flex md:flex-col">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-sm font-semibold">Thirdy</span>
          <div className="flex items-center gap-2">
            {user && (
              <span className="text-xs text-muted-foreground truncate max-w-[120px]">
                {user.name}
              </span>
            )}
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={logout}>
              Logout
            </Button>
          </div>
        </div>
        <ConversationList />
      </aside>

      {/* Mobile sidebar */}
      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              className="absolute left-2 top-2 z-10 md:hidden"
            />
          }
        >
          <span className="text-lg">☰</span>
        </SheetTrigger>
        <SheetContent side="left" className="w-[280px] p-0">
          <SheetTitle className="border-b px-4 py-3 text-sm font-semibold">
            Thirdy
          </SheetTitle>
          <ConversationList />
        </SheetContent>
      </Sheet>

      {/* Main content */}
      {children}
    </div>
  );
}
