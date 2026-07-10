import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

export function usePredictions() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ homeTeamId, awayTeamId }: { homeTeamId: number; awayTeamId: number }) =>
      api.predictMatch(homeTeamId, awayTeamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bracket'] });
    },
  });
}
