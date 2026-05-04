import React from 'react';
import GuestStudentPreview from './guest-student-preview';
import type { PublicSection } from '@/lib/route-utils';

interface PublicEntryProps {
  section: PublicSection;
}

export default function PublicEntry({ section }: PublicEntryProps) {
  return <GuestStudentPreview section={section} />;
}
