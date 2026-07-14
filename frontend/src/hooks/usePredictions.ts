import { useMutation } from '@tanstack/react-query';
import { api } from '../services/api';

export function usePredictions() {
  return useMutation({
    mutationFn: ({ simulationId, matchKey }: { simulationId: string; matchKey: string }) =>
      api.predictMatch(simulationId, matchKey),
  });
}
