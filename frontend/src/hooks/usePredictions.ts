import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

export function usePredictions() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ simulationId, matchKey }: { simulationId: string; matchKey: string }) =>
      api.predictMatch(simulationId, matchKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bracket'] });
    },
  });
}
