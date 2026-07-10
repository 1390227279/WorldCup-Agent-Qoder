import { useQuery } from '@tanstack/react-query';
import { fetchBracket } from '../services/api';

export function useBracket() {
  return useQuery({
    queryKey: ['bracket'],
    queryFn: fetchBracket,
    staleTime: 5 * 60 * 1000,
  });
}
