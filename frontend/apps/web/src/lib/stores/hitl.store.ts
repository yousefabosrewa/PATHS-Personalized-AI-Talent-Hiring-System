"use client";

import { create } from "zustand";
import type { HITLApproval } from "@/types";

interface HITLState {
  activeApproval: HITLApproval | null;
  panelOpen: boolean;
  openPanel: (approval: HITLApproval) => void;
  closePanel: () => void;
}

export const useHITLStore = create<HITLState>()((set) => ({
  activeApproval: null,
  panelOpen: false,

  openPanel: (approval) => set({ activeApproval: approval, panelOpen: true }),
  closePanel: () => set({ activeApproval: null, panelOpen: false }),
}));
