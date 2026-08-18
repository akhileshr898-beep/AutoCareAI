document.addEventListener("DOMContentLoaded", () => {
    initialiseProfileMenu();
    initialiseRevealAnimations();
    initialiseCounters();
});


function initialiseProfileMenu() {
    const profileButton =
        document.getElementById("profileButton");

    const profileDropdown =
        document.getElementById("profileDropdown");

    if (!profileButton || !profileDropdown) {
        return;
    }

    profileButton.addEventListener("click", event => {
        event.stopPropagation();

        profileDropdown.classList.toggle("open");
    });

    document.addEventListener("click", event => {
        if (
            !profileDropdown.contains(event.target)
            && !profileButton.contains(event.target)
        ) {
            profileDropdown.classList.remove("open");
        }
    });
}


function initialiseRevealAnimations() {
    const cards =
        document.querySelectorAll(".reveal-card");

    if (!("IntersectionObserver" in window)) {
        cards.forEach(card => {
            card.classList.add("visible");
        });

        return;
    }

    const observer = new IntersectionObserver(
        entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) {
                    return;
                }

                entry.target.classList.add("visible");
                observer.unobserve(entry.target);
            });
        },
        {
            threshold: 0.08
        }
    );

    cards.forEach((card, index) => {
        card.style.transitionDelay =
            `${Math.min(index * 65, 300)}ms`;

        observer.observe(card);
    });
}


function initialiseCounters() {
    const counters =
        document.querySelectorAll(".counter");

    counters.forEach(counter => {
        const target =
            Number(counter.dataset.target || 0);

        animateCounter(counter, target);
    });
}


function animateCounter(element, target) {
    const duration = 900;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;

        const progress =
            Math.min(elapsed / duration, 1);

        const eased =
            1 - Math.pow(1 - progress, 3);

        element.textContent =
            Math.floor(target * eased);

        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = target;
        }
    }

    requestAnimationFrame(update);
}