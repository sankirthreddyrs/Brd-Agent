import axios from 'axios';

/**
 * Base API URL resolved from environment variable VITE_API_URL,
 * with fallback to local FastAPI server http://localhost:8000.
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
