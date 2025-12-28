import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler
from src import image_generator, video_generator

# Logger
logger = logging.getLogger(__name__)

# States
EDIT_MENU, EDIT_IMG, EDIT_TITLE, EDIT_SUB, EDIT_COLOR, EDIT_HIGHLIGHT, EDIT_PADDING = range(7)

async def start_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for editing a generated news post."""
    query = update.callback_query
    logger.info(f"Edit Handler triggered! Data: {query.data}")
    await query.answer()
    
    # Ensure we have context data
    if 'last_gen_params' not in context.user_data:
        logger.warning("No last_gen_params found in context.")
        await query.message.reply_text("❌ Session expired or no data found to edit.")
        return ConversationHandler.END
    
    # Show Edit Menu
    await show_edit_menu(update, context)
    return EDIT_MENU

async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the current parameters and edit buttons."""
    params = context.user_data['last_gen_params']
    
    msg_text = (
        "🛠️ **Edit Manual Post**\n"
        f"**Headline**: {params.get('title')[:30]}...\n"
        f"**Sub**: {params.get('summary')[:30]}...\n"
        f"**Color**: {params.get('manual_color', 'Auto')}\n"
        f"**Highlight**: {params.get('highlight_text', 'Auto')}\n\n"
        "What would you like to change?"
    )
    
    keyboard = [
        [InlineKeyboardButton("🖼️ Change Image", callback_data='edit_img')],
        [InlineKeyboardButton("T Headlines", callback_data='edit_title'), InlineKeyboardButton("S Subheading", callback_data='edit_sub')],
        [InlineKeyboardButton("🖍️ Highlight Words", callback_data='edit_highlight'), InlineKeyboardButton("🎨 Highlight Color", callback_data='edit_color')],
        [InlineKeyboardButton("📐 Padding", callback_data='edit_padding')], 
        [InlineKeyboardButton("✅ Done / Regenerate", callback_data='edit_done')]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_caption(caption=msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def edit_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles menu selection."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'edit_img':
        await query.message.reply_text("📤 Please upload a new **Image** or **Video** (or type 'skip' to remove).")
        return EDIT_IMG
        
    elif data == 'edit_title':
        await query.message.reply_text("📝 Enter the new **Headline**:")
        return EDIT_TITLE
        
    elif data == 'edit_sub':
        await query.message.reply_text("📝 Enter the new **Subheading/Summary**:")
        return EDIT_SUB
        
    elif data == 'edit_highlight':
        await query.message.reply_text("🖍️ Type the **End Word/Phrase**.\n(Highlight will start from the beginning and end at your matched text)")
        return EDIT_HIGHLIGHT
        
    elif data == 'edit_color':
        await query.message.reply_text("🎨 Enter Color (Hex or Name) or 'auto':")
        return EDIT_COLOR
        
    elif data == 'edit_padding':
        keyboard = [
            [InlineKeyboardButton("Tight (3px)", callback_data='pad_3')],
            [InlineKeyboardButton("Standard (6px)", callback_data='pad_6')],
            [InlineKeyboardButton("Loose (12px)", callback_data='pad_12')],
            [InlineKeyboardButton("Custom", callback_data='pad_custom')]
        ]
        await query.message.reply_text("📐 Choose **Box Padding**:", reply_markup=InlineKeyboardMarkup(keyboard))
        return EDIT_PADDING
        
    elif data == 'edit_done':
        await re_render_image(update, context)
        return ConversationHandler.END
        
    return EDIT_MENU

async def handle_edit_highlight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['last_gen_params']['highlight_text'] = text
    await update.message.reply_text(f"✅ Highlight set to: '{text}'")
    return await prompt_return_to_menu(update, context)

async def handle_edit_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Video Update
    if update.message.video:
        video_file = await update.message.video.get_file()
        
        # Save to temp
        import os, uuid
        temp_dir = os.path.join(os.getcwd(), 'temp_videos')
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.mp4"
        video_path = os.path.join(temp_dir, filename)
        
        # Use safe download
        await video_file.download_to_drive(custom_path=video_path)
            
        context.user_data['last_gen_params']['manual_video'] = video_path
        context.user_data['last_gen_params']['create_video_path'] = video_path # Sync keys
        context.user_data['last_gen_params']['manual_image'] = None # Clear image
        context.user_data['last_gen_params']['image_url'] = None
        
        await update.message.reply_text("✅ Video updated.")
        
    # 2. Image Update  
    elif update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        file_bytearray = await photo_file.download_as_bytearray()
        from PIL import Image
        import io
        image_obj = Image.open(io.BytesIO(file_bytearray))
        context.user_data['last_gen_params']['manual_image'] = image_obj
        context.user_data['last_gen_params']['image_url'] = None
        context.user_data['last_gen_params']['manual_video'] = None # Clear video
        context.user_data['last_gen_params']['create_video_path'] = None
        
        await update.message.reply_text("✅ Image updated.")
        
    elif update.message.text.lower() == 'skip':
        context.user_data['last_gen_params']['manual_image'] = None
        context.user_data['last_gen_params']['manual_video'] = None
        context.user_data['last_gen_params']['create_video_path'] = None
        await update.message.reply_text("✅ Visuals cleared.")
        
    return await prompt_return_to_menu(update, context)

async def handle_edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_gen_params']['title'] = update.message.text
    await update.message.reply_text("✅ Headline updated.")
    return await prompt_return_to_menu(update, context)

async def handle_edit_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_gen_params']['summary'] = update.message.text
    await update.message.reply_text("✅ Subheading updated.")
    return await prompt_return_to_menu(update, context)

async def handle_edit_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text.lower() == 'auto':
        context.user_data['last_gen_params']['manual_color'] = None
        await update.message.reply_text("✅ Color resetting to Auto.")
        return await prompt_return_to_menu(update, context)
        
    # Try Hex first
    if text.startswith('#'):
        context.user_data['last_gen_params']['manual_color'] = text
        await update.message.reply_text(f"✅ Color updated to {text}.")
        return await prompt_return_to_menu(update, context)
        
    # Try Extended HTML Name Search
    from src.components.colors import parse_color_name
    hex_code, name_found = parse_color_name(text)
    
    if hex_code:
        context.user_data['last_gen_params']['manual_color'] = hex_code
        await update.message.reply_text(f"✅ Color updated to **{name_found}** ({hex_code}).")
        return await prompt_return_to_menu(update, context)
        
    # Try Standard PIL Parsing (Fallback)
    from PIL import ImageColor
    try:
        rgb = ImageColor.getrgb(text)
        context.user_data['last_gen_params']['manual_color'] = rgb
        await update.message.reply_text(f"✅ Color updated to {text} ({rgb}).")
        return await prompt_return_to_menu(update, context)
    except ValueError:
        pass
        
    await update.message.reply_text("⚠️ Invalid Color. Use Hex (#FF0000) or Name (Red). Keeping previous.")
    return await prompt_return_to_menu(update, context)

async def handle_edit_padding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles padding selection."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == 'pad_custom':
             await query.message.reply_text("🔢 Type a number for padding (pixels):")
             return EDIT_PADDING
             
        # Parse value map
        val_map = {'pad_3': 3, 'pad_6': 6, 'pad_12': 12}
        val = val_map.get(data, 6)
        
        context.user_data['last_gen_params']['highlight_padding'] = val
        await query.message.reply_text(f"✅ Padding set to {val}px.")
        return await prompt_return_to_menu(update, context)
    
    # Handle text input (Custom)
    if update.message and update.message.text:
        try:
            val = int(update.message.text.strip())
            context.user_data['last_gen_params']['highlight_padding'] = val
            await update.message.reply_text(f"✅ Padding set to {val}px.")
        except ValueError:
            await update.message.reply_text("❌ Invalid number. Defaulting to 6px.")
            context.user_data['last_gen_params']['highlight_padding'] = 6
    
    return await prompt_return_to_menu(update, context)

async def prompt_return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the menu again after an edit."""
    # We can't edit the old photo caption easily if it scrolled up.
    # Send a fresh menu message
    params = context.user_data['last_gen_params']
    msg_text = (
        "🛠️ **Edit Manual Post**\n"
        f"**Headline**: {params.get('title')[:30]}...\n"
        f"**Sub**: {params.get('summary')[:30]}...\n"
        f"**Color**: {params.get('manual_color', 'Auto')}\n"
        f"**Highlight**: {params.get('highlight_text', 'Auto')}\n\n"
        "Ready to render?"
    )
    keyboard = [
        [InlineKeyboardButton("🖼️ Change Image", callback_data='edit_img')],
        [InlineKeyboardButton("T Headlines", callback_data='edit_title'), InlineKeyboardButton("S Subheading", callback_data='edit_sub')],
        [InlineKeyboardButton("🖍️ Highlight Words", callback_data='edit_highlight'), InlineKeyboardButton("🎨 Highlight Color", callback_data='edit_color')],
        [InlineKeyboardButton("📐 Padding", callback_data='edit_padding')], 
        [InlineKeyboardButton("✅ Done / Regenerate", callback_data='edit_done')]
    ]
    
    # Determine target message
    if update.message:
        target_msg = update.message
    elif update.callback_query and update.callback_query.message:
        target_msg = update.callback_query.message
    else:
        logger.error("No target message found for prompt_return_to_menu")
        return EDIT_MENU

    await target_msg.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return EDIT_MENU

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Edit cancelled.")
    return ConversationHandler.END

# Helper for safe editing
async def safe_edit_text(message, text):
    try:
        if message.text != text:
            await message.edit_text(text)
    except Exception as e:
        logger.warning(f"Safe edit ignored: {e}")

async def re_render_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Regenerates the image/video with updated params."""
    query = update.callback_query
    status_msg = await query.message.reply_text("🎨 Re-rendering...")
    
    params = context.user_data.get('last_gen_params', {})
    
    try:
        # Check for Video first
        manual_video = params.get('manual_video') or params.get('create_video_path')
        
        if manual_video:
            # Re-render Video
            await safe_edit_text(status_msg, "🎬 Re-processing video...")
            
            # Hide date for videos
            date_str = "" 
            
            overlay_io = image_generator.create_overlay_image(
                title=params.get('title'),
                summary=params.get('summary'),
                date_str=date_str,
                source=params.get('source', 'Edited'),
                manual_color=params.get('manual_color'),
                highlight_text=params.get('highlight_text'),
                highlight_padding=params.get('highlight_padding')
            )
            
            if overlay_io:
                final_path = video_generator.process_video_with_overlay(manual_video, overlay_io)
                if final_path:
                    await status_msg.delete()
                    keyboard = [[InlineKeyboardButton("✏️ Edit Again", callback_data='edit_start')]]
                    await query.message.reply_video(
                        video=open(final_path, 'rb'),
                        caption=f"✨ Updated Video: {params.get('summary')}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await safe_edit_text(status_msg, "❌ Video processing failed.")
            else:
                 await safe_edit_text(status_msg, "❌ Overlay generation failed.")
                 
        else:
            # Re-render Image
            img_io = image_generator.create_news_image(
                title=params.get('title'),
                source=params.get('source', 'Edited'),
                date_str=params.get('date_str', ''),
                image_url=params.get('image_url'),
                summary=params.get('summary'),
                manual_image=params.get('manual_image'),
                manual_color=params.get('manual_color'),
                highlight_text=params.get('highlight_text'),
                highlight_padding=params.get('highlight_padding')
            )
            
            if img_io:
                await status_msg.delete()
                # Send new photo with Edit button again
                keyboard = [[InlineKeyboardButton("✏️ Edit Again", callback_data='edit_start')]]
                await query.message.reply_photo(
                    photo=img_io, 
                    caption=f"✨ Updated: {params.get('summary')}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await status_msg.edit_text("❌ Generation failed.")
            
    except Exception as e:
        logger.error(f"Re-render error: {e}")
        await status_msg.edit_text("❌ Error during generation.")

# ... (Cancel Edit) ...

# Export the Handler
edit_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_callback, pattern=re.compile(r'^edit_start'))],
    states={
        EDIT_MENU: [CallbackQueryHandler(edit_menu_handler)],
        EDIT_IMG: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.TEXT & ~filters.COMMAND, handle_edit_img)],
        EDIT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_title)],
        EDIT_SUB: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_sub)],
        EDIT_HIGHLIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_highlight)],
        EDIT_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_color)],
        EDIT_PADDING: [
            CallbackQueryHandler(handle_edit_padding, pattern='^pad_'), 
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_padding)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_edit)]
)
