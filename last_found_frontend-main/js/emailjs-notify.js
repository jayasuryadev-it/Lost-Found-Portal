/* ═══════════════════════════════════════════════════════════
   Lost & Found Portal — EmailJS Integration
   Service ID: service_rf42fqn
   Template ID: template_znf1vsp
   ═══════════════════════════════════════════════════════════ */

// IMPORTANT: Replace this with your actual EmailJS Public Key
const EMAILJS_PUBLIC_KEY = 'dVkqwqLEa_-B3daUK';
const EMAILJS_SERVICE_ID = 'service_rf42fqn';
const EMAILJS_TEMPLATE_ID = 'template_znf1vsp';

/**
 * Initialize EmailJS (call once on page load)
 */
function initEmailJS() {
    if (typeof emailjs !== 'undefined') {
        emailjs.init(EMAILJS_PUBLIC_KEY);
        console.log('EmailJS initialized');
    } else {
        console.warn('EmailJS SDK not loaded');
    }
}

/**
 * Send email notification when someone claims to have found a lost item
 * @param {Object} params
 * @param {string} params.to_email   - Item owner's email
 * @param {string} params.to_name    - Item owner's name
 * @param {string} params.item_title - Title of the lost item
 * @param {string} params.finder_name  - Name of the person who found it
 * @param {string} params.finder_email - Email of the finder
 * @param {string} params.message    - Optional message from finder
 */
async function sendFoundNotification(params) {
    if (typeof emailjs === 'undefined') {
        console.error('EmailJS SDK not loaded');
        showToast('Email service not available', 'error');
        return false;
    }

    try {
        const templateParams = {
            to_email: params.to_email,
            to_name: params.to_name,
            item_title: params.item_title,
            finder_name: params.finder_name,
            finder_email: params.finder_email,
            message: params.message || 'I found your item! Please contact me.',
        };

        const result = await emailjs.send(
            EMAILJS_SERVICE_ID,
            EMAILJS_TEMPLATE_ID,
            templateParams
        );

        console.log('Email sent successfully:', result);
        showToast('Notification email sent to the item owner!', 'success');
        return true;
    } catch (error) {
        console.error('Failed to send email:', error);
        showToast('Failed to send email notification. The item has still been marked as found.', 'error');
        return false;
    }
}
