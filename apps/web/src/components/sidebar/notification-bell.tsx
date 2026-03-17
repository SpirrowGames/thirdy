"use client";

import { useState } from "react";
import { useNotifications } from "@/hooks/use-notifications";

export function NotificationBell() {
  const { notifications, unreadCount, markRead, markAllRead, dismiss } = useNotifications();
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative text-sm"
        title={`${unreadCount} unread notifications`}
      >
        <span className={unreadCount > 0 ? "" : "opacity-40"}>
          {"\u{1F514}"}
        </span>
        {unreadCount > 0 && (
          <span className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed left-2 top-12 z-50 w-80 rounded-lg border bg-background shadow-lg">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-xs font-semibold">Notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="text-[10px] text-muted-foreground hover:text-foreground"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-64 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="p-4 text-center text-xs text-muted-foreground">
                No notifications
              </p>
            ) : (
              notifications.slice(0, 20).map((n) => (
                <div
                  key={n.id}
                  className={`border-b px-3 py-2 text-xs ${n.is_read ? "opacity-60" : ""}`}
                >
                  <div className="flex items-start justify-between gap-1">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{n.title}</p>
                      {n.body && (
                        <p className="mt-0.5 text-muted-foreground line-clamp-2">{n.body}</p>
                      )}
                      <p className="mt-1 text-[10px] text-muted-foreground">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      {!n.is_read && (
                        <button
                          onClick={() => markRead(n.id)}
                          className="text-[10px] text-blue-500 hover:underline"
                        >
                          Read
                        </button>
                      )}
                      <button
                        onClick={() => dismiss(n.id)}
                        className="text-[10px] text-muted-foreground hover:text-foreground"
                      >
                        x
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
