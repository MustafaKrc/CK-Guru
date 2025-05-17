"use client";

import { useEffect } from 'react';
import { useTaskStore } from '@/store/taskStore'; // Adjust path as needed
// import { useAuth } from '@/components/auth/auth-provider'; // If connection depends on auth status

export function GlobalAppEffects() {
  const connectSSE = useTaskStore((state) => state.connectSSE);
  const disconnectSSE = useTaskStore((state) => state.disconnectSSE);
  // const { isAuthenticated } = useAuth(); // Uncomment if using auth to gate connection

  useEffect(() => {
    // Example: Connect SSE if user is authenticated, or always if public
    // if (isAuthenticated) {
    //   console.log("User authenticated, attempting to connect SSE.");
    //   connectSSE();
    // } else {
    //   console.log("User not authenticated, disconnecting SSE if active.");
    //   disconnectSSE();
    // }

    // For now, let's assume we always want to try connecting if the app is loaded by a client.
    // If your SSE endpoint is protected by auth, this needs to be tied to auth state.
    console.log("GlobalAppEffects: Attempting to connect SSE on mount.");
    connectSSE();

    return () => {
      // This cleanup runs when the component unmounts.
      // For a truly global effect, this component would live as long as the app.
      // If you want to disconnect when the browser tab is closed, that's harder to manage reliably.
      // Disconnecting here might be too aggressive if it unmounts on page navigation.
      // Consider if disconnectSSE should only be called on explicit logout or app termination.
      // For now, let's not disconnect on unmount of this specific component,
      // but rather rely on explicit disconnect calls (e.g., on logout).
      // console.log("GlobalAppEffects: Cleaning up on unmount (optional SSE disconnect).");
      // disconnectSSE(); 
    };
  }, [connectSSE, disconnectSSE /*, isAuthenticated */]); // Add isAuthenticated if used

  return null; // This component does not render any UI
}