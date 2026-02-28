import axios from 'axios';
import type { ParcelDetail, SearchResponse, DashboardStats } from './types';

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001',
});

export const api = {
  searchParcels: (params: {
    state?: string;
    county?: string;
    decision?: string;
    review_status?: string;
    search_term?: string;
    sort_by?: string;
    limit?: number;
    offset?: number;
  }) => API.get<SearchResponse>('/scrapers/parcels/search', { params }),

  getParcelDetail: (id: number) =>
    API.get<ParcelDetail>(`/scrapers/parcels/detail/${id}`),

  updateAssessment: (parcelId: number, data: Record<string, unknown>) =>
    API.put(`/scrapers/assessments/${parcelId}`, data),

  getDashboard: (state: string, county: string) =>
    API.get<DashboardStats>(`/scrapers/dashboard/${state}/${county}`),
};
