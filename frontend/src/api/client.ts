import axios from 'axios';
import { supabase } from './supabase';

/**
 * Base API URL resolved from environment variable VITE_API_URL,
 * with fallback to local FastAPI server http://localhost:8000.
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ||
  (typeof window !== 'undefined' && window.location.hostname && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1'
    ? `http://${window.location.hostname}:8000`
    : 'http://localhost:8000');

/**
 * Shared Axios HTTP client configured for BRD Agent backend communication.
 */
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60 seconds timeout for LLM analysis / compilation
});

// Request interceptor to attach active Supabase JWT
apiClient.interceptors.request.use(async (config) => {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    // Proceed without authorization header if session lookup fails
  }
  return config;
});

// Response interceptor for consistent error extraction
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorDetail =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected network error occurred';
    return Promise.reject(new Error(errorDetail));
  }
);

export default apiClient;
