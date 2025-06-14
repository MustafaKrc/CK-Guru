// lib/paginationUtils.ts

export const generatePagination = (
  currentPage: number,
  totalPages: number
): (number | string)[] => {
  // If there are 7 or less pages, show all of them
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  // If the current page is near the start
  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, "...", totalPages];
  }

  // If the current page is near the end
  if (currentPage > totalPages - 4) {
    return [1, "...", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
  }

  // If the current page is in the middle
  return [1, "...", currentPage - 1, currentPage, currentPage + 1, "...", totalPages];
};
