document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const navbar = document.getElementById("mainNav");
    const navbarCollapse = document.getElementById("mainNavbar");
    const revealElements = Array.from(
        document.querySelectorAll(".reveal")
    );

    // NAVBAR SCROLL EFFECT
    const updateNavbar = () => {
        if (!navbar) return;

        navbar.classList.toggle(
            "scrolled",
            window.scrollY > 24
        );
    };

    updateNavbar();

    window.addEventListener(
        "scroll",
        updateNavbar,
        { passive: true }
    );


    // REVEAL ANIMATION
    const showElement = (element) => {
        if (!element) return;
        element.classList.add("visible");
    };

    if ("IntersectionObserver" in window) {

        const revealObserver = new IntersectionObserver(
            (entries, observer) => {

                entries.forEach((entry) => {

                    if (!entry.isIntersecting) return;

                    showElement(entry.target);
                    observer.unobserve(entry.target);
                });

            },
            {
                threshold: 0.04,
                rootMargin: "0px 0px 80px 0px"
            }
        );

        revealElements.forEach((element) => {
            revealObserver.observe(element);
        });


        // Immediately show visible content
        requestAnimationFrame(() => {

            revealElements.forEach((element) => {

                const rect =
                    element.getBoundingClientRect();

                if (
                    rect.top <
                    window.innerHeight + 100 &&
                    rect.bottom > -100
                ) {

                    showElement(element);

                    revealObserver.unobserve(
                        element
                    );
                }
            });

        });


        // Safety fallback
        setTimeout(() => {

            revealElements.forEach(
                showElement
            );

        }, 1400);

    } else {

        revealElements.forEach(
            showElement
        );
    }


    // SMOOTH SCROLL
    const internalLinks =
        document.querySelectorAll(
            'a[href^="#"]:not([href="#"])'
        );

    internalLinks.forEach((link) => {

        link.addEventListener(
            "click",
            (event) => {

                const selector =
                    link.getAttribute("href");

                if (!selector) return;

                let target = null;

                try {

                    target =
                        document.querySelector(
                            selector
                        );

                } catch (error) {

                    console.warn(
                        "Invalid anchor:",
                        selector
                    );

                    return;
                }

                if (!target) return;

                event.preventDefault();

                target.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });


                if (history.pushState) {

                    history.pushState(
                        null,
                        "",
                        selector
                    );
                }


                // Close mobile navbar
                if (
                    navbarCollapse &&
                    navbarCollapse.classList.contains(
                        "show"
                    ) &&
                    window.bootstrap
                ) {

                    const collapse =
                        bootstrap.Collapse
                            .getOrCreateInstance(
                                navbarCollapse
                            );

                    collapse.hide();
                }
            }
        );
    });


    // ACTIVE NAVBAR SECTION
    const sectionLinks =
        Array.from(
            document.querySelectorAll(
                '.premium-navbar .nav-link[href^="#"]'
            )
        );


    const trackedSections =
        sectionLinks
            .map((link) => {

                const selector =
                    link.getAttribute("href");

                if (!selector) return null;

                let section = null;

                try {

                    section =
                        document.querySelector(
                            selector
                        );

                } catch (error) {

                    return null;
                }

                if (!section)
                    return null;

                return {
                    link,
                    section
                };

            })
            .filter(Boolean);


    const updateActiveSection = () => {

        const position =
            window.scrollY + 150;

        sectionLinks.forEach(
            (link) => {
                link.classList.remove(
                    "active"
                );
            }
        );

        let active = null;

        trackedSections.forEach(
            (item) => {

                if (
                    item.section.offsetTop <=
                    position
                ) {

                    active = item;
                }

            }
        );

        if (active) {
            active.link.classList.add(
                "active"
            );
        }
    };


    updateActiveSection();

    window.addEventListener(
        "scroll",
        updateActiveSection,
        { passive: true }
    );


    // DIRECT URL HASH SUPPORT
    if (window.location.hash) {

        const hash =
            window.location.hash;

        try {

            const target =
                document.querySelector(
                    hash
                );

            if (target) {

                requestAnimationFrame(
                    () => {

                        target
                            .querySelectorAll(
                                ".reveal"
                            )
                            .forEach(
                                showElement
                            );

                        target.scrollIntoView({
                            behavior: "auto",
                            block: "start"
                        });

                    }
                );
            }

        } catch (error) {

            console.warn(
                "Could not open section:",
                hash
            );
        }
    }

});