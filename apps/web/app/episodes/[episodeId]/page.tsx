import { EpisodeDetailView } from "@/components/episode-detail";

type Props = {
  params: Promise<{ episodeId: string }>;
};

export default async function EpisodeDetailPage({ params }: Props) {
  const { episodeId } = await params;
  return <EpisodeDetailView episodeId={episodeId} />;
}

