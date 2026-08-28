import axios from "axios";

// All requests go through the Nginx gateway at the same origin as the frontend
// (see gateway/nginx.conf), so no absolute host/port needs to be configured here —
// this works identically in docker-compose, Kubernetes, and `vite dev` (proxied).
export const documentsApi = axios.create({ baseURL: "/api/documents" });
export const vendorsApi = axios.create({ baseURL: "/api/vendors" });
export const approvalsApi = axios.create({ baseURL: "/api/approvals" });
export const inventoryApi = axios.create({ baseURL: "/api/inventory" });
export const contractsApi = axios.create({ baseURL: "/api/contracts" });
export const riskApi = axios.create({ baseURL: "/api/risk" });
export const notificationsApi = axios.create({ baseURL: "/api/notifications" });
