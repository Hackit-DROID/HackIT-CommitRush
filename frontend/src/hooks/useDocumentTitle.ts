import { useEffect } from 'react';

/**
 * Custom hook to dynamically update document title and meta description on route changes.
 * Preserves the previous title upon unmount if desired, or sets unique page-specific metadata.
 */
export function useDocumentTitle(title: string, description?: string) {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = title;

    let metaDesc = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    const previousDesc = metaDesc ? metaDesc.getAttribute('content') : null;

    if (description) {
      if (!metaDesc) {
        metaDesc = document.createElement('meta');
        metaDesc.setAttribute('name', 'description');
        document.head.appendChild(metaDesc);
      }
      metaDesc.setAttribute('content', description);
    }

    return () => {
      document.title = previousTitle;
      if (metaDesc && previousDesc !== null) {
        metaDesc.setAttribute('content', previousDesc);
      }
    };
  }, [title, description]);
}
