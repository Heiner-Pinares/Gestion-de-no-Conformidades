(() => {
  const views = document.querySelectorAll('[data-registro-view]');

  views.forEach((view) => {
    const tableScroll = view.querySelector('[data-registro-scroll]');
    const topScroll = view.querySelector('[data-registro-scroll-top]');
    const track = view.querySelector('[data-registro-scroll-track]');
    const table = view.querySelector('.registro-tabla');
    const startButton = view.querySelector('[data-registro-start]');
    const endButton = view.querySelector('[data-registro-end]');

    if (!tableScroll || !topScroll || !track || !table) return;

    let synchronizing = false;

    const updateTrack = () => {
      track.style.width = `${table.scrollWidth}px`;
    };

    const synchronize = (source, target) => {
      if (synchronizing) return;
      synchronizing = true;
      target.scrollLeft = source.scrollLeft;
      window.requestAnimationFrame(() => { synchronizing = false; });
    };

    const moveTo = (left) => {
      synchronizing = true;
      tableScroll.scrollLeft = left;
      topScroll.scrollLeft = left;
      window.requestAnimationFrame(() => { synchronizing = false; });
    };

    tableScroll.addEventListener('scroll', () => synchronize(tableScroll, topScroll), { passive: true });
    topScroll.addEventListener('scroll', () => synchronize(topScroll, tableScroll), { passive: true });
    startButton?.addEventListener('click', () => moveTo(0));
    endButton?.addEventListener('click', () => moveTo(tableScroll.scrollWidth));

    const resetToFirstColumn = () => {
      updateTrack();
      tableScroll.scrollLeft = 0;
      topScroll.scrollLeft = 0;
    };

    window.addEventListener('pageshow', resetToFirstColumn);
    window.addEventListener('resize', updateTrack, { passive: true });
    new ResizeObserver(updateTrack).observe(table);
    window.requestAnimationFrame(resetToFirstColumn);
  });
})();
