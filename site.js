(() => {
  const toggle = document.querySelector('[data-menu-toggle]');
  const nav = document.querySelector('[data-mobile-nav]');
  const body = document.body;

  const closeMenu = () => {
    if (!toggle || !nav) return;
    toggle.setAttribute('aria-expanded', 'false');
    nav.classList.remove('is-open');
    body.classList.remove('nav-open');
  };

  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      nav.classList.toggle('is-open', !open);
      body.classList.toggle('nav-open', !open);
    });
    nav.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
    window.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeMenu();
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth >= 980) closeMenu();
    });
  }

  document.querySelectorAll('[data-reveal-request]').forEach(control => {
    control.addEventListener('click', event => {
      event.preventDefault();
      const panel = document.querySelector('#request-form');
      if (!panel) return;
      panel.hidden = false;
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      window.setTimeout(() => panel.querySelector('input, select, textarea')?.focus(), 450);
    });
  });

  const form = document.querySelector('[data-preview-form]');
  if (form) {
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const status = form.querySelector('[data-form-status]');
      if (status) {
        status.hidden = false;
        status.textContent = 'Thank you. This preview form is working visually, but no information has been sent or stored.';
        status.focus?.();
      }
    });
  }

  document.querySelectorAll('[data-year]').forEach(node => {
    node.textContent = new Date().getFullYear();
  });
})();
