// Shared navigation toggle for all pages
document.addEventListener('DOMContentLoaded', function () {
    const toggle = document.getElementById('nav-toggle');
    const links = document.getElementById('nav-links');
    if (toggle && links) {
        toggle.addEventListener('click', function () {
            const isOpen = links.classList.toggle('open');
            toggle.setAttribute('aria-expanded', isOpen);
            toggle.textContent = isOpen ? '✕' : '☰';
        });
        // Close nav on link click (mobile)
        links.querySelectorAll('.nav-link').forEach(function (link) {
            link.addEventListener('click', function () {
                links.classList.remove('open');
                toggle.setAttribute('aria-expanded', 'false');
                toggle.textContent = '☰';
            });
        });
    }
});
