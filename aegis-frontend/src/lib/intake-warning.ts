export function buildEvidenceStatus({
  uploaded,
  total,
}: {
  uploaded: number;
  total: number;
}): { ok: boolean; label: string; detail: string } {
  const safeTotal = Math.max(total, 0);
  const safeUploaded = Math.max(Math.min(uploaded, safeTotal), 0);
  const ok = safeTotal > 0 && safeUploaded === safeTotal;

  return {
    ok,
    label: ok ? "Required evidence complete" : "Required evidence incomplete",
    detail: `${safeUploaded} of ${safeTotal} required artifacts uploaded`,
  };
}

export function buildRequiredArtifactState({
  isDemo,
  datasetUploaded,
  mddUploaded,
  trainingCodeUploaded,
}: {
  isDemo: boolean;
  datasetUploaded: boolean;
  mddUploaded: boolean;
  trainingCodeUploaded: boolean;
}): {
  uploaded: number;
  total: number;
  label: string;
  detail: string;
  ok: boolean;
  missingRequiredArtifacts: string[];
  trainingCodeStatus: "Pending" | "Not supplied — demo" | "Uploaded";
} {
  const required = isDemo
    ? [
        { key: "dataset", label: "Validation Dataset", ready: datasetUploaded },
        { key: "mdd", label: "Model Development Document", ready: mddUploaded },
      ]
    : [
        { key: "dataset", label: "Validation Dataset", ready: datasetUploaded },
        { key: "mdd", label: "Model Development Document", ready: mddUploaded },
        { key: "training", label: "Training Code / Scripts", ready: trainingCodeUploaded },
      ];

  const missingRequiredArtifacts = required.filter((artifact) => !artifact.ready).map((artifact) => artifact.label);
  const uploaded = required.filter((artifact) => artifact.ready).length;
  const total = required.length;
  const evidenceStatus = buildEvidenceStatus({ uploaded, total });

  return {
    uploaded,
    total,
    label: evidenceStatus.label,
    detail: evidenceStatus.detail,
    ok: evidenceStatus.ok,
    missingRequiredArtifacts,
    trainingCodeStatus: isDemo ? "Not supplied — demo" : trainingCodeUploaded ? "Uploaded" : "Pending",
  };
}

export function buildSubmissionBlockedReason({
  metadataReady,
  missingRequiredArtifacts,
  allAttested,
  chkAttestation,
}: {
  metadataReady: boolean;
  missingRequiredArtifacts: string[];
  allAttested: boolean;
  chkAttestation: boolean;
}): string | null {
  const prettyArtifactName = (label: string): string => {
    const normalized = label.trim();
    if (!normalized) return "required artifact";
    if (normalized.toLowerCase() === "training code / scripts") return "training code / scripts";
    if (normalized.toLowerCase() === "validation dataset") return "validation dataset";
    if (normalized.toLowerCase() === "model development document") return "MDD";
    return normalized.toLowerCase();
  };

  const artifactMessage = missingRequiredArtifacts.length > 0
    ? `Upload the required ${missingRequiredArtifacts.length === 1
      ? prettyArtifactName(missingRequiredArtifacts[0])
      : `${missingRequiredArtifacts.slice(0, -1).map(prettyArtifactName).join(", ")} and ${prettyArtifactName(missingRequiredArtifacts[missingRequiredArtifacts.length - 1])}`
    } to proceed.`
    : null;

  const governanceMessage = !allAttested ? "Complete all governance controls." : null;
  const metadataMessage = !metadataReady ? "Complete the required model metadata." : null;
  const attestationMessage = !chkAttestation ? "Confirm the intake is accurate and complete." : null;

  const parts = [metadataMessage, artifactMessage, governanceMessage, attestationMessage].filter(Boolean) as string[];
  return parts.length > 0 ? parts.join(" ") : null;
}
