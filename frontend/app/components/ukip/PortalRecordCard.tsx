import type { ComponentProps } from "react";
import RecordResultCard from "../RecordResultCard";

export default function PortalRecordCard(props: ComponentProps<typeof RecordResultCard>) {
  return <RecordResultCard {...props} />;
}

