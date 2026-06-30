"use client";

import { Bell, LogOut, User as UserIcon, Settings, ChevronDown } from "lucide-react";
import { motion } from "framer-motion";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/stores/auth.store";
import { usePendingApprovals } from "@/lib/hooks";
import { initials } from "@/lib/utils/format";
import { useRouter } from "next/navigation";

export function Header() {
  const { user, logout } = useAuthStore();
  const { data: pending = [] } = usePendingApprovals();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-end border-b border-border/50 bg-background/80 px-6 backdrop-blur-sm">
      {/* Right side */}
      <div className="flex items-center gap-2">
        {/* HITL notification bell */}
        <Button
          variant="ghost"
          size="icon"
          className="relative h-9 w-9 text-muted-foreground hover:text-foreground"
          onClick={() => router.push("/approvals")}
        >
          <Bell className="h-4 w-4" />
          {pending.length > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-bold text-primary-foreground"
            >
              {pending.length}
            </motion.span>
          )}
        </Button>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <button className="flex h-9 items-center gap-2 rounded-lg px-2 text-sm font-medium hover:bg-muted/40 transition-colors">
                <Avatar className="h-7 w-7">
                  <AvatarImage src={user?.avatar} alt={user?.name} />
                  <AvatarFallback className="bg-primary/10 text-primary text-[11px]">
                    {initials(user?.name ?? "U")}
                  </AvatarFallback>
                </Avatar>
                <div className="hidden flex-col items-start md:flex">
                  <span className="text-[13px] font-semibold leading-tight text-foreground">{user?.name}</span>
                  <span className="text-[10px] leading-tight text-muted-foreground capitalize">{user?.role?.replace("_", " ")}</span>
                </div>
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              </button>
            }
          />
          <DropdownMenuContent className="w-52">
            <DropdownMenuGroup>
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-0.5">
                  <p className="text-sm font-semibold">{user?.name}</p>
                  <p className="text-xs text-muted-foreground">{user?.email}</p>
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem className="gap-2 text-sm cursor-pointer">
                <UserIcon className="h-3.5 w-3.5" /> Profile
              </DropdownMenuItem>
              <DropdownMenuItem
                className="gap-2 text-sm cursor-pointer"
                onClick={() => router.push("/settings/organization")}
              >
                <Settings className="h-3.5 w-3.5" /> Settings
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem
                className="gap-2 text-sm text-destructive focus:text-destructive cursor-pointer"
                onClick={handleLogout}
              >
                <LogOut className="h-3.5 w-3.5" /> Log out
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
