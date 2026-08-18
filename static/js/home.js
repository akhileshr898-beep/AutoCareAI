document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const navbar =
        document.getElementById("mainNav");

    const navbarCollapse =
        document.getElementById("mainNavbar");

    const revealElements =
        Array.from(
            document.querySelectorAll(".reveal")
        );


    // ==========================================
    // NAVBAR SCROLL EFFECT
    // ==========================================

    const updateNavbar = () => {

        if (!navbar) {
            return;
        }

        if (window.scrollY > 24) {

            navbar.classList.add(
                "scrolled"
            );

        } else {

            navbar.classList.remove(
                "scrolled"
            );
        }
    };


    updateNavbar();


    window.addEventListener(
        "scroll",
        updateNavbar,
        {
            passive: true
        }
    );


    // ==========================================
    // SAFE REVEAL ANIMATION
    // ==========================================

    const showElement = (element) => {

        if (!element) {
            return;
        }

        element.classList.add(
            "visible"
        );
    };


    if (
        "IntersectionObserver"
        in window
    ) {

        const revealObserver =
            new IntersectionObserver(

                (entries, observer) => {

                    entries.forEach(
                        (entry) => {

                            if (
                                !entry.isIntersecting
                            ) {
                                return;
                            }

                            showElement(
                                entry.target
                            );

                            observer.unobserve(
                                entry.target
                            );
                        }
                    );

                },

                {
                    threshold: 0.04,

                    rootMargin:
                        "0px 0px 80px 0px"
                }
            );


        revealElements.forEach(
            (element) => {

                revealObserver.observe(
                    element
                );
            }
        );


        // Immediately show elements
        // already visible on screen

        requestAnimationFrame(
            () => {

                revealElements.forEach(
                    (element) => {

                        const rect =
                            element.getBoundingClientRect();

                        if (
                            rect.top <
                            window.innerHeight + 100
                            &&
                            rect.bottom > -100
                        ) {

                            showElement(
                                element
                            );

                            revealObserver.unobserve(
                                element
                            );
                        }
                    }
                );
            }
        );


        // Fail-safe:
        // never allow page to remain blank

        setTimeout(
            () => {

                revealElements.forEach(
                    showElement
                );

            },
            1200
        );

    } else {

        revealElements.forEach(
            showElement
        );
    }


    // ==========================================
    // SMOOTH INTERNAL LINKS
    // ==========================================

    const internalLinks =
        document.querySelectorAll(
            'a[href^="#"]:not([href="#"])'
        );


    internalLinks.forEach(
        (link) => {

            link.addEventListener(
                "click",
                (event) => {

                    const selector =
                        link.getAttribute(
                            "href"
                        );

                    if (!selector) {
                        return;
                    }


                    let target = null;


                    try {

                        target =
                            document.querySelector(
                                selector
                            );

                    } catch (error) {

                        console.warn(
                            "Invalid section:",
                            selector
                        );

                        return;
                    }


                    if (!target) {
                        return;
                    }


                    event.preventDefault();


                    target.scrollIntoView({
                        behavior: "smooth",
                        block: "start"
                    });


                    if (
                        history.pushState
                    ) {

                        history.pushState(
                            null,
                            "",
                            selector
                        );
                    }


                    // Close Bootstrap mobile menu

                    if (
                        navbarCollapse
                        &&
                        navbarCollapse
                            .classList
                            .contains("show")
                        &&
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
        }
    );


    // ==========================================
    // ACTIVE NAVIGATION SECTION
    // ==========================================

    const sectionLinks =
        Array.from(
            document.querySelectorAll(
                '.premium-navbar .nav-link[href^="#"]'
            )
        );


    const trackedSections =
        sectionLinks

            .map(
                (link) => {

                    const selector =
                        link.getAttribute(
                            "href"
                        );


                    if (!selector) {
                        return null;
                    }


                    let section = null;


                    try {

                        section =
                            document.querySelector(
                                selector
                            );

                    } catch (error) {

                        return null;
                    }


                    if (!section) {
                        return null;
                    }


                    return {

                        link: link,

                        section: section
                    };
                }
            )

            .filter(Boolean);


    const updateActiveSection =
        () => {

            if (
                trackedSections.length
                === 0
            ) {
                return;
            }


            const position =
                window.scrollY + 150;


            let active = null;


            trackedSections.forEach(
                (item) => {

                    if (
                        item.section.offsetTop
                        <= position
                    ) {

                        active = item;
                    }
                }
            );


            sectionLinks.forEach(
                (link) => {

                    link.classList.remove(
                        "active"
                    );
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
        {
            passive: true
        }
    );


    // ==========================================
    // DIRECT HASH URL SUPPORT
    // Example:
    // /#features
    // ==========================================

    if (window.location.hash) {

        const hash =
            window.location.hash;


        try {

            const target =
                document.querySelector(
                    hash
                );


            if (target) {

                target
                    .querySelectorAll(
                        ".reveal"
                    )
                    .forEach(
                        showElement
                    );


                requestAnimationFrame(
                    () => {

                        target.scrollIntoView({
                            behavior: "auto",
                            block: "start"
                        });
                    }
                );
            }

        } catch (error) {

            console.warn(
                "Unable to open section:",
                hash
            );
        }
    }


    console.log(
        "AutoCare AI home.js loaded successfully"
    );

});