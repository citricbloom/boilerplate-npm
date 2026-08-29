(() => {
  const header = document.querySelector('[data-header]');
  const menuToggle = document.querySelector('[data-menu-toggle]');
  const mobileMenu = document.querySelector('[data-mobile-menu]');
  const layer = document.querySelector('[data-contact-layer]');
  const openButtons = document.querySelectorAll('[data-open-contact]');
  const closeButtons = document.querySelectorAll('[data-close-contact]');
  const options = document.querySelector('[data-contact-options]');
  const form = document.querySelector('[data-contact-form]');
  const success = document.querySelector('[data-form-success]');
  const formBack = document.querySelector('[data-form-back]');
  const showFormButtons = document.querySelectorAll('[data-show-form]');
  const formEyebrow = document.querySelector('[data-form-eyebrow]');
  const formTitle = document.querySelector('[data-form-title]');
  const formIntro = document.querySelector('[data-form-intro]');
  let lastFocused = null;

  const onScroll = () => header?.classList.toggle('is-scrolled', window.scrollY > 16);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  const closeMenu = () => {
    if (!mobileMenu || !menuToggle) return;
    mobileMenu.hidden = true;
    menuToggle.setAttribute('aria-expanded', 'false');
  };

  menuToggle?.addEventListener('click', () => {
    const willOpen = mobileMenu.hidden;
    mobileMenu.hidden = !willOpen;
    menuToggle.setAttribute('aria-expanded', String(willOpen));
  });

  mobileMenu?.querySelectorAll('a, button').forEach((el) => el.addEventListener('click', closeMenu));

  const resetPanel = () => {
    if (options) options.hidden = false;
    if (form) form.hidden = true;
    if (success) success.hidden = true;
  };

  const openContact = () => {
    if (!layer) return;
    lastFocused = document.activeElement;
    resetPanel();
    layer.hidden = false;
    document.body.classList.add('no-scroll');
    requestAnimationFrame(() => layer.querySelector('[data-close-contact]')?.focus());
  };

  const closeContact = () => {
    if (!layer) return;
    layer.hidden = true;
    document.body.classList.remove('no-scroll');
    lastFocused?.focus?.();
  };

  openButtons.forEach((button) => button.addEventListener('click', openContact));
  closeButtons.forEach((button) => button.addEventListener('click', closeContact));

  showFormButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const mode = button.dataset.showForm;
      if (mode === 'message') {
        formEyebrow.textContent = 'Send a message';
        formTitle.textContent = 'Leave your details';
        formIntro.textContent = 'Tell us how you would prefer to be contacted. You can keep the message brief.';
      } else {
        formEyebrow.textContent = 'Initial Wellbeing Consultation';
        formTitle.textContent = 'Request your first conversation';
        formIntro.textContent = 'Leave the minimum details required for the Polaris team to contact you.';
      }
      options.hidden = true;
      form.hidden = false;
      form.querySelector('input')?.focus();
    });
  });

  formBack?.addEventListener('click', resetPanel);

  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    form.hidden = true;
    success.hidden = false;
    success.querySelector('button')?.focus();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && layer && !layer.hidden) closeContact();
  });

  const observer = 'IntersectionObserver' in window
    ? new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12 })
    : null;

  document.querySelectorAll('.reveal').forEach((el) => {
    if (observer) observer.observe(el);
    else el.classList.add('is-visible');
  });
})();
