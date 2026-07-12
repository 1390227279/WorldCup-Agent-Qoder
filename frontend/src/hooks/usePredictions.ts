import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import type { Team } from '../types';

export function usePredictions() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ homeTeam, awayTeam }: { homeTeam: Team; awayTeam: Team }) =>
      api.predictMatch(homeTeam, awayTeam),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bracket'] });
    },
  });
}
