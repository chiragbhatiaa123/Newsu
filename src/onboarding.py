import logging
import os
import shutil
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from src import database as db
from src import image_generator

logger = logging.getLogger(__name__)

# Constants
USER_DATA_DIR = "users_data"
DEFAULT_CONFIG_PATH = os.path.join("config", "template_config.json")

# Conversation States
# Conversation States
OB_WELCOME, OB_PAGE_NAME, OB_LOGO, OB_FONTS_PROMPT, OB_FONTS_UPLOAD, OB_PREVIEW = range(6)
OB_ADJUST_MENU, OB_ADJUST_H_SIZE, OB_ADJUST_S_SIZE, OB_ADJUST_COLOR, OB_ADJUST_GRADIENT = range(6, 11)

def get_user_dir(user_id):
    path = os.path.join(USER_DATA_DIR, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path

def get_user_config_path(user_id):
    return os.path.join(get_user_dir(user_id), "template_config.json")

def load_user_config(user_id):
    path = get_user_config_path(user_id)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    # If not exists, return default (loaded fresh)
    with open(DEFAULT_CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_user_config(user_id, config):
    try:
        path = get_user_config_path(user_id)
        with open(path, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Failed to save config for {user_id}: {e}")
        return False

# Handlers
async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point check."""
    user = update.effective_user
    user_id = user.id
    
    # 1. Check if we have a config
    config_path = get_user_config_path(user_id)
    if os.path.exists(config_path):
         await update.message.reply_text(
             f"👋 **Welcome Back, {user.first_name}!**\n\n"
             "Your brand is set up.\n"
             "🔹 **/start_news** - Begin receiving updates\n"
             "🔹 **/stop_news** - Pause updates\n"
             "🔹 **/reset** - Delete setup and start fresh\n"
             "🔹 **/create** - Manually generate post"
         )
         return ConversationHandler.END
         
    # 2. Start Setup
    await update.message.reply_text(
        f"👋 Welcome to **NewsU**!\n\n"
        "Let's set up your personal **Brand Template**.\n"
        "I'll ask for your Page Name, Logo, and details.\n\n"
        "Ready?",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Start Setup", callback_data='ob_start')]])
    )
    return OB_WELCOME

async def ob_welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.message.reply_text("1️⃣ First, what is the **Name of your Page/Brand**?\n_(This is used for record keeping)_")
    return OB_PAGE_NAME

async def ob_page_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data['ob_page_name'] = name
    
    await update.message.reply_text(
        f"✅ Nice to meet you, **{name}**.\n\n"
        "2️⃣ Now, please upload your **Logo** (PNG with Transparent Background).\n"
        "_(Send it as a File/Document for best quality, or just an Image)_"
    )
    return OB_LOGO

async def ob_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo_file = None
    
    if update.message.document:
        doc = update.message.document
        if 'image' in doc.mime_type or doc.file_name.lower().endswith('.png'):
             photo_file = await doc.get_file()
        else:
            await update.message.reply_text("❌ Please upload a PNG image file.")
            return OB_LOGO
            
    elif update.message.photo:
         photo_file = await update.message.photo[-1].get_file()
         
    if not photo_file:
         await update.message.reply_text("❌ No image found. Please upload your logo.")
         return OB_LOGO
         
    # Save Logo
    user_dir = get_user_dir(user_id)
    logo_path = os.path.join(user_dir, "logo.png")
    
    await photo_file.download_to_drive(logo_path)
    context.user_data['ob_logo_path'] = logo_path
    
    await update.message.reply_text(
        "✅ Logo saved!\n\n"
        "3️⃣ **Fonts**\n"
        "Do you want to use a **Custom Font** for headlines?\n"
        "_(If No, I'll use the default bold font)_",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Upload Font (.ttf)", callback_data='ob_font_yes')],
            [InlineKeyboardButton("Use Default", callback_data='ob_font_no')]
        ])
    )
    return OB_FONTS_PROMPT

async def ob_fonts_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'ob_font_yes':
        await query.message.reply_text("📤 Please upload your **.ttf** or **.otf** font file.")
        return OB_FONTS_UPLOAD
    else:
        context.user_data['ob_font_path'] = None
        # Default font is already in the default config, we just won't override it
        return await trigger_preview(update, context)

async def ob_fonts_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not update.message.document:
        await update.message.reply_text("❌ Please upload a Font file (document).")
        return OB_FONTS_UPLOAD
        
    doc = update.message.document
    name = doc.file_name.lower()
    if not (name.endswith('.ttf') or name.endswith('.otf')):
         await update.message.reply_text("❌ Invalid format. Please upload .ttf or .otf")
         return OB_FONTS_UPLOAD
         
    font_file = await doc.get_file()
    user_dir = get_user_dir(user_id)
    font_dest = os.path.join(user_dir, "headline_font.ttf") # rename for simplicity
    await font_file.download_to_drive(font_dest)
    
    context.user_data['ob_font_path'] = font_dest
    await update.message.reply_text("✅ Font received.")
    
    return await trigger_preview(update, context)

async def trigger_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves config, Renders Preview, Shows Adjustment Menu."""
    user_id = update.effective_user.id
    msg_or_query = update.message if update.message else update.callback_query.message
    
    # 1. Update & Save Config
    base_config = load_user_config(user_id) 
    
    # Apply context changes if any (from initial setup)
    if 'ob_logo_path' in context.user_data:
        base_config['logo']['path'] = context.user_data['ob_logo_path']
    if context.user_data.get('ob_font_path'):
        base_config['fonts']['headline_path'] = context.user_data['ob_font_path']
    base_config['page_name'] = context.user_data.get('ob_page_name', base_config.get('page_name', 'My Page'))
    
    save_user_config(user_id, base_config)
    
    # 2. Render Preview (Real)
    status_msg = await msg_or_query.reply_text("🎨 Generating Preview...")
    
    try:
        from src import image_generator
        # Dummy Content
        img_io = image_generator.create_news_image(
            title="Welcome to NewsU", 
            source=base_config['page_name'],
            date_str="Now",
            image_url=None, # Will use gradient default
            summary="This is how your news posts will look. You can adjust fonts and colors below.",
            user_id=user_id
        )
        
        await status_msg.delete()
        
        if img_io:
            caption = (
                "📝 **Template Preview**\n\n"
                "Adjust settings before finishing:"
            )
            keyboard = [
                [InlineKeyboardButton("📏 Heading Size", callback_data='adj_h_size'), InlineKeyboardButton("📏 Sub Size", callback_data='adj_s_size')],
                [InlineKeyboardButton("🎨 Highlight Color", callback_data='adj_color'), InlineKeyboardButton("↕️ Gradient", callback_data='adj_grad')],
                [InlineKeyboardButton("✅ Finish Setup", callback_data='ob_finish')]
            ]
            await msg_or_query.reply_photo(photo=img_io, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
            return OB_ADJUST_MENU
        else:
             await msg_or_query.reply_text("❌ Preview generation failed. Please check your assets.")
             return OB_ADJUST_MENU

    except Exception as e:
        logger.error(f"Preview Error: {e}")
        await msg_or_query.reply_text("❌ Error generating preview.")
        return OB_ADJUST_MENU

# --- Adjustment Handlers ---

async def adj_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'adj_h_size':
        await query.message.reply_text("📏 Enter new **Heading Font Size** (current default is usually ~60-80):")
        return OB_ADJUST_H_SIZE
        
    elif data == 'adj_s_size':
        await query.message.reply_text("📏 Enter new **Subheading Font Size** (current default is usually ~30-40):")
        return OB_ADJUST_S_SIZE
        
    elif data == 'adj_color':
        await query.message.reply_text("🎨 Enter **Default Highlight Color** (Hex code e.g. #FF0000):")
        return OB_ADJUST_COLOR
        
    elif data == 'adj_grad':
        # Simple toggle or prompt? Let's prompt for height ratio
        await query.message.reply_text("↕️ Enter **Gradient Height Ratio** (0.0 to 1.0).\n(Smaller = Lower gradient, Larger = Higher up coverage. Default ~0.5)")
        return OB_ADJUST_GRADIENT
        
    elif data == 'ob_finish':
        return await ob_finish(update, context)
        
    return OB_ADJUST_MENU

async def adj_save_h_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        size = int(update.message.text.strip())
        user_id = update.effective_user.id
        config = load_user_config(user_id)
        
        # Match src/components/headline.py key
        if 'fonts' not in config: config['fonts'] = {}
        config['fonts']['headline_size_start'] = size
        
        save_user_config(user_id, config)
        await update.message.reply_text(f"✅ Heading Size set to {size}.")
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")
    return await trigger_preview(update, context)

async def adj_save_s_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        size = int(update.message.text.strip())
        user_id = update.effective_user.id
        config = load_user_config(user_id)
        
        # Match src/components/footer.py key
        if 'subheading' not in config: config['subheading'] = {}
        config['subheading']['font_size'] = size
        
        save_user_config(user_id, config)
        await update.message.reply_text(f"✅ Subheading Size set to {size}.")
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")
    return await trigger_preview(update, context)

async def adj_save_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith('#') and len(text) in [4, 7]:
        user_id = update.effective_user.id
        config = load_user_config(user_id)
        
        # Convert hex to RGB list logic could be here, but config implies storing config values
        # The generator expects RGB list usually in ['colors']['accent_default']
        # Let's simple store it as hex or list. Generator handles lists.
        # Let's parse hex to [r, g, b]
        h = text.lstrip('#')
        rgb = [int(h[i:i+2], 16) for i in (0, 2, 4)]
        
        config['colors']['accent_default'] = rgb
        save_user_config(user_id, config)
        await update.message.reply_text(f"✅ Default Color set to {text}.")
    else:
        await update.message.reply_text("❌ Invalid Hex Code.")
    return await trigger_preview(update, context)

async def adj_save_gradient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.strip())
        if 0.1 <= val <= 1.0:
            user_id = update.effective_user.id
            config = load_user_config(user_id)
            # Assuming config structure has gradient settings
            # We usually use 'gradient_height_ratio' or 'start_ratio' in prepare_background?
            # Looking at create_gradient_overlay in background.py...
            
            # Let's save it to a new key if needed, or existing.
            # config['canvas']['gradient_height_ratio'] = val ... 
            # I need to ensure background.py uses this.
            if 'canvas' not in config: config['canvas'] = {}
            config['canvas']['gradient_height'] = val 
            
            save_user_config(user_id, config)
            await update.message.reply_text(f"✅ Gradient Height set to {val}.")
        else:
             await update.message.reply_text("❌ Value must be between 0.1 and 1.0")
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")
    return await trigger_preview(update, context)


async def ob_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Final Config Save (Clean up temp keys if any)
    # Already saved during adjustments.
    
    await query.message.reply_text(
        "🎉 **Setup Complete!**\n\n"
        "Use configuration has been saved.\n"
        "👉 Type **/start_news** to select your region and begin fetching.\n"
        "👉 Type **/create** to make a post manually."
    )
    return ConversationHandler.END

async def cancel_ob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Setup cancelled.")
    return ConversationHandler.END

# Handler Registry
onboarding_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start_onboarding)],
    states={
        OB_WELCOME: [CallbackQueryHandler(ob_welcome_handler, pattern='^ob_start$')],
        OB_PAGE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_page_name)],
        OB_LOGO: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, ob_logo)],
        OB_FONTS_PROMPT: [CallbackQueryHandler(ob_fonts_prompt, pattern='^ob_font_')],
        OB_FONTS_UPLOAD: [MessageHandler(filters.Document.ALL, ob_fonts_upload)],
        OB_PREVIEW: [CallbackQueryHandler(ob_finish, pattern='^ob_finish$')], # Fallback if direct finish
        
        OB_ADJUST_MENU: [
            CallbackQueryHandler(adj_menu_handler, pattern='^adj_'),
            CallbackQueryHandler(ob_finish, pattern='^ob_finish$')
        ],
        OB_ADJUST_H_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, adj_save_h_size)],
        OB_ADJUST_S_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, adj_save_s_size)],
        OB_ADJUST_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, adj_save_color)],
        OB_ADJUST_GRADIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adj_save_gradient)]
    },
    fallbacks=[CommandHandler("cancel", cancel_ob)]
)
