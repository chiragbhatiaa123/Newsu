import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from src import database as db
from src import fetcher, x_fetcher, gemini_utils, image_generator, image_searcher, video_fetcher, video_generator, image_picker
from src.config import TELEGRAM_TOKEN
from src.edit_handler import edit_conv_handler
# Updated logger
logger = logging.getLogger(__name__)

# Conversation States
CREATE_IMG, CREATE_TITLE, CREATE_SUB, CREATE_COLOR = range(4)

# --- Keyboards ---
def get_unit_keyboard():
    keyboard = [
        [InlineKeyboardButton("Global / Major", callback_data='unit_major')],
        [InlineKeyboardButton("India", callback_data='unit_india')],
        [InlineKeyboardButton("Specific City", callback_data='unit_city_prompt')],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Create Handlers ---
async def start_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start manual creation flow."""
    await update.message.reply_text(
        "🛠️ **Manual News Creator**\n\n"
        "Let's build a post! First, upload an **Image** or **Video**.\n"
        "_(Or type 'skip' to use a default gradient)_",
        parse_mode='Markdown'
    )
    return CREATE_IMG

async def create_handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle image/video upload."""
    
    # 1. Video Upload
    if update.message.video:
        video_file = await update.message.video.get_file()
        
        # Save to temp file
        import os
        import uuid
        temp_dir = os.path.join(os.getcwd(), 'temp_videos')
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.mp4"
        video_path = os.path.join(temp_dir, filename)
        
        # Use download_to_drive handling timeouts better
        await video_file.download_to_drive(custom_path=video_path)
            
        context.user_data['create_video_path'] = video_path
        context.user_data['create_img'] = None # Clear image
        
        await update.message.reply_text("🎥 Video received! I'll overlay news on it.\n\nNow, enter the **Headline**:")
        return CREATE_TITLE

    # 2. Image Upload
    if update.message.photo:
        # Get highest res photo
        photo_file = await update.message.photo[-1].get_file()
        
        # Stream to memory using download_as_bytearray is fine for images (usually <10MB)
        # But for robustness let's just use it, or continue.
        # Actually images rarely timeout. The traceback specifically mentioned VIDEO.
        # I'll keep image as bytearray for convenience with PIL.
        
        file_bytearray = await photo_file.download_as_bytearray()
        
        # Convert to PIL Image
        from PIL import Image
        import io
        image_obj = Image.open(io.BytesIO(file_bytearray))
        context.user_data['create_img'] = image_obj
        context.user_data['create_video_path'] = None # Clear video
        await update.message.reply_text("✅ Image received!\n\nNow, enter the **Headline**:")
        
    elif update.message.text and update.message.text.lower() == 'skip':
        context.user_data['create_img'] = None
        context.user_data['create_video_path'] = None
        await update.message.reply_text("⏩ Image skipped.\n\nNow, enter the **Headline**:")
    else:
        await update.message.reply_text("❌ Please upload an image, video, or type 'skip'.")
        return CREATE_IMG
        
    return CREATE_TITLE

async def create_handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['create_title'] = text
    await update.message.reply_text("✅ Headline set.\n\nNow, enter the **Subheading/Summary**:")
    return CREATE_SUB

async def create_handle_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['create_sub'] = text
    await update.message.reply_text(
        "✅ Subheading set.\n\nFinally, pick a **Highlight Color**:\n"
        "- Type a Hex Code (e.g. `#FF0000`)\n"
        "- Type `auto` to pick from image",
        parse_mode='Markdown'
    )
    return CREATE_COLOR

async def create_handle_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    color_input = None
    
    if text.lower() != 'auto':
        # 1. Try Hex
        if text.startswith('#') and len(text) in [4, 7]:
            color_input = text
        else:
            # 2. Try Name
            try:
                from PIL import ImageColor
                color_input = ImageColor.getrgb(text)
            except ValueError:
                await update.message.reply_text("⚠️ Invalid Color. Using 'auto' instead.")
            
    # Generate
    manual_img = context.user_data.get('create_img')
    manual_video = context.user_data.get('create_video_path')
    title = context.user_data.get('create_title')
    sub = context.user_data.get('create_sub')
    
    status_msg = await update.message.reply_text("🎨 Rendering your custom post...")
    
    try:
        import datetime
        date_str = datetime.datetime.now().strftime("%d %b, %Y")
        
        if manual_video:
            # Video Flow
            import os
            
            # 1. Create Overlay
            await safe_edit_text(status_msg, "🎨 Creating overlay...")
            overlay_io = image_generator.create_overlay_image(
                title=title,
                summary=sub,
                date_str="", # Hide date for video
                source="Manual",
                manual_color=color_input
            )
            
            if overlay_io:
                # 2. Process Video
                await safe_edit_text(status_msg, "🎬 Processing video (Crop & Merge)...")
                final_video_path = video_generator.process_video_with_overlay(manual_video, overlay_io)
                
                if final_video_path and os.path.exists(final_video_path):
                    await status_msg.delete()
                    await update.message.reply_video(video=open(final_video_path, 'rb'), caption="✨ Here is your custom video!")
                    # Cleanup final video (and maybe raw video if needed)
                    # For now keep raw if we want to support edit, but manual flow ends here.
                else:
                    await status_msg.edit_text("❌ Video processing failed.")
            else:
                await status_msg.edit_text("❌ Overlay generation failed.")
                
        else:
            # Image Flow
            img_io = image_generator.create_news_image(
                title=title,
                source="Manual",
                date_str=date_str,
                image_url=None, 
                summary=sub,
                manual_image=manual_img,
                manual_color=color_input
            )
            
            if img_io:
                await status_msg.delete()
                await update.message.reply_photo(photo=img_io, caption="✨ Here is your custom post!")
            else:
                await status_msg.edit_text("❌ Generation failed.")
            
    except Exception as e:
        logger.error(f"Manual Gen Error: {e}")
        await status_msg.edit_text("❌ Error occurred.")

    return ConversationHandler.END

async def cancel_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Creation cancelled.")
    return ConversationHandler.END

# --- Command Handlers ---
# --- Command Handlers ---
# /start handled by onboarding.py


async def start_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable news fetching."""
    await update.message.reply_text(
        "🌍 **Select News Region:**\n"
        "Choose a unit to start receiving updates:",
        reply_markup=get_unit_keyboard()
    )

async def stop_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable news fetching."""
    user_id = update.effective_user.id
    db.update_user_unit(user_id, 'none')
    await update.message.reply_text("🛑 News updates stopped. Use /start_news to resume.")

async def reset_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset user config and unit."""
    user_id = update.effective_user.id
    
    # 1. Update DB
    db.update_user_unit(user_id, 'none')
    
    # 2. Delete Folder
    import shutil
    import os
    user_dir = os.path.join("users_data", str(user_id))
    if os.path.exists(user_dir):
        try:
            shutil.rmtree(user_dir)
        except Exception as e:
            logger.error(f"Reset delete failed: {e}")
            
    await update.message.reply_text(
        "🔄 **Reset Complete.**\n"
        "Your settings and assets have been cleared.\n\n"
        "Type /start to set up again."
    )

# --- Command Handlers ---
# Note: /start is handled by onboarding_conv_handler

async def update_news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual trigger for news update."""
    await update.message.reply_text("Checking for news updates...")
    # Trigger the news job immediately for *this* user only or all?
    # Context suggests "if asked exciluy by the user by the function update".
    # I'll update for ALL users to keep state consistent and simple, 
    # or just this user. Let's do just this user for immediate feedback.
    user_id = update.effective_user.id
    unit = db.get_user_unit(user_id)
    
    # Reuse the fetch logic but specifically for this user
    try:
        items = fetcher.fetch_news_for_unit(unit)
        if not items:
            await update.message.reply_text("No new news at the moment.")
            return

        # Limit manual update to avoiding spamming (e.g. max 5 items)
        if len(items) > 5:
            items = items[:5]
            await update.message.reply_text(f"Found {len(items)}+ updates. Showing top 5:")

        for item in items:
            summary_part = f"\n\n_{item.get('summary', '')}_" if item.get('summary') else ""
            msg = f"*{item['title']}*{summary_part}\n\n{item['published']}\n[Read more]({item['link']})"
            keyboard = [
                [InlineKeyboardButton("✨ Generate Copy", callback_data='copy_trigger')],
                [InlineKeyboardButton("🎨 Generate Image", callback_data='img_trigger')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await context.bot.send_message(
                    chat_id=user_id, 
                    text=msg, 
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                db.mark_news_as_seen(item['link'])
            except Exception as e:
                logger.error(f"Failed to send manual update to {user_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in manual update: {e}")
        await update.message.reply_text("An error occurred while fetching news.")

# Helper for safe editing
async def safe_edit_text(message, text):
    try:
        if message.text != text:
            await message.edit_text(text)
    except Exception as e:
        logger.warning(f"Safe edit ignored: {e}")

# --- Handlers ---

# --- New Helper for Image Selection ---
async def send_image_selection_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    picker = context.user_data.get('image_picker')
    if not picker:
        await update.effective_message.reply_text("❌ Image picker session expired.")
        return

    status_msg = await update.effective_message.reply_text("🔍 Fetching best images (Google + Pinterest)...")
    
    # Fetch batch
    images = await picker.fetch_next_batch(5)
    
    if not images:
        await status_msg.edit_text("⚠️ No more unique images found. Please pick from previous or skip.")
        return # Should probably show "Skip" button here at least, but let's assume valid flow
        
    context.user_data['current_batch_images'] = images
    await status_msg.delete()
    
    # Send Images as an album or individual? 
    # User said "presented with 5 images... then continues"
    # Sending 5 images individually might be spammy but ensures visibility. 
    # Use MediaGroup if possible? But they need to be numbered.
    # Easiest: Send 5 individual photos with numbers in caption? Or just send them and then the menu.
    
    from telegram import InputMediaPhoto
    media_group = []
    
    # Actually, to let user pick "1, 2, 3", the images need to be easily identified.
    # Sending 5 individual images with "Option 1", "Option 2" is clearest.
    
    # Calculate global start index for this batch
    global_start_idx = len(picker.cached_images) - len(images)
    
    # Send Images
    for i, url in enumerate(images):
        global_idx = global_start_idx + i
        
        try:
             # Caption with global option number
             caption = f"Option {global_idx + 1}"
             # Create individual select button with Global Index
             btn = InlineKeyboardButton(f"✅ Select Option {global_idx + 1}", callback_data=f'img_pick_{global_idx}')
             await update.effective_message.reply_photo(
                 photo=url, 
                 caption=caption,
                 reply_markup=InlineKeyboardMarkup([[btn]])
             )
        except Exception as e:
            logger.error(f"Failed to send image {url}: {e}")
            
    # Send Selection Keyboard with Global Indices
    # Map buttons 1-5 to the current batch's global indices
    row1 = []
    row2 = []
    
    # helper to safely add button if index exists in this batch
    for i in range(5):
        if i < len(images):
            g_idx = global_start_idx + i
            label = str(g_idx + 1)
            btn = InlineKeyboardButton(label, callback_data=f'img_pick_{g_idx}')
            if i < 3:
                row1.append(btn)
            else:
                row2.append(btn)

    keyboard = []
    if row1: keyboard.append(row1)
    if row2: keyboard.append(row2)
    
    keyboard.append([InlineKeyboardButton("🔄 Show 5 More", callback_data='img_more')])
    keyboard.append([InlineKeyboardButton("⏩ Skip / Use AI", callback_data='img_skip')])
    
    await update.effective_message.reply_text(
        "✨ **Scroll up to pick an image above**\nOr use options below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def perform_final_render(update: Update, context: ContextTypes.DEFAULT_TYPE, image_url=None, auto_search=False):
    """
    Renders the final image. 
    If image_url is provided, uses it.
    If auto_search is True, searches Google for an image first.
    """
    query = update.callback_query
    status_msg = await query.message.reply_text("🎨 Finalizing Render...")
    
    # Retrieve params
    params = context.user_data.get('pending_render_params')
    if not params:
         await status_msg.edit_text("❌ Render session expired.")
         return

    title = params['title']
    summary = params['summary']
    date_str = params['date_str']
    style_name = params.get('style_name', 'Custom')
    
    final_image_url = image_url
    
    # Auto Search if needed
    if auto_search and not final_image_url:
        await safe_edit_text(status_msg, "🔍 AI is picking an image...")
        serp_candidates = image_searcher.search_google_images(title)
        if serp_candidates:
            # Simple validation logic (copied from original)
            for url in serp_candidates:
                 # We skip strict validation for speed/robustness here or use verify_image_usability
                if gemini_utils.verify_image_usability(url, title):
                    final_image_url = url
                    break
    
    # Render
    await safe_edit_text(status_msg, "🎨 Rendering Image...")
    img_io = image_generator.create_news_image(title, "Newsu", date_str, final_image_url, summary=summary)
    
    if img_io:
        await status_msg.delete()
        
        context.user_data['last_gen_params'] = {
            'title': title,
            'summary': summary,
            'source': "Newsu",
            'date_str': date_str,
            'image_url': final_image_url,
            'manual_image': None,
            'manual_color': None
        }
        
        caption = f"Generated ({style_name}): {summary}"
        if style_name == 'Custom':
            caption = "✨ Draft. Click 'Edit' to customize text!"
        
        keyboard = [[InlineKeyboardButton("✏️ Edit", callback_data='edit_start')]]
        await query.message.reply_photo(photo=img_io, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await safe_edit_text(status_msg, "❌ Render failed.")

# --- Callback Handlers ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == 'unit_city_prompt':
        # Prompt user to type city name
        context.user_data['waiting_for_city'] = True
        await query.edit_message_text(text="Please type the name of the city:")
        
    elif data.startswith('copy_'):
        status_msg = await query.message.reply_text("✨ Generating copy...")
        message_text = query.message.text
        if message_text:
            lines = message_text.split('\n')
            title = lines[0]
            summary = gemini_utils.generate_copy(title, "News Source")
            await safe_edit_text(status_msg, f"📝 *Copy Suggestion:*\n\n{summary}")
        else:
            await safe_edit_text(status_msg, "❌ Could not read original message.")
            
    elif data == 'img_trigger':
        # Step 1: Generate Variations
        status_msg = await query.message.reply_text("✨ Generating style options...")
        message_text = query.message.text
        
        if not message_text:
             await safe_edit_text(status_msg, "❌ Could not read message.")
             return

        # Prefer scraped data if available
        scraped_item = context.user_data.get('last_scraped_item', {})
        if scraped_item:
            title = scraped_item.get('title')
            context_text = scraped_item.get('content') or scraped_item.get('summary') or message_text
            date_str = scraped_item.get('published', 'Latest News')
        else:
            # Fallback to parsing message
            lines = [l.strip() for l in message_text.split('\n') if l.strip()]
            title = lines[0]
            context_text = message_text
            
            date_str = "Latest News"
            for l in reversed(lines):
                 if len(l) < 30 and any(c.isdigit() for c in l): 
                     date_str = l
                     break
        
        # Call Gemini for 4 variations
        variations = gemini_utils.generate_all_variations(title, context_text)
        
        if not variations or not isinstance(variations, dict):
            await safe_edit_text(status_msg, "❌ Failed to generate styles.")
            return

        # Save context
        context.user_data['img_gen_context'] = {
            'variations': variations,
            'date_str': date_str,
            'original_title': title # Fallback for Custom
        }
        
        # Format the Preview Message
        preview_text = "✨ **Choose a Style:**\n\n"
        
        styles_map = ['Professional', 'Narrative', 'Simple', 'Casual']
        
        for i, style in enumerate(styles_map):
            var = variations.get(style, {})
            h = var.get('headline', 'N/A')
            s = var.get('sub', 'N/A')
            preview_text += f"{i+1}. **{style}**\n   H: _{h}_\n   S: _{s}_\n\n"
            
        preview_text += "Or custom input?"
        
        keyboard = [
            [InlineKeyboardButton("1. Pro", callback_data='var_Professional'), InlineKeyboardButton("2. Narrative", callback_data='var_Narrative')],
            [InlineKeyboardButton("3. Simple", callback_data='var_Simple'), InlineKeyboardButton("4. Casual", callback_data='var_Casual')],
            [InlineKeyboardButton("✍️ Custom", callback_data='style_custom')]
        ]
        
        # We edit the status message if possible, or send new one
        await status_msg.edit_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data.startswith('var_') or data == 'style_custom':
        # Step 2: Render Selection
        ctx_data = context.user_data.get('img_gen_context')
        if not ctx_data and data != 'style_custom': # custom might work loosely
            await query.message.reply_text("❌ Session expired.")
            return

        status_msg = await query.message.reply_text("🎨 Starting Render...")
        
        final_title = ""
        final_sub = ""
        style_name = "Custom"
        
        if data == 'style_custom':
            # Use raw or simple base, then trigger edit
            final_title = ctx_data['original_title'] if ctx_data else "Your Headline"
            final_sub = "Your Subheading"
        else:
            style_name = data.replace('var_', '')
            var = ctx_data['variations'].get(style_name, {})
            final_title = var.get('headline', ctx_data['original_title'])
            final_sub = var.get('sub', '')

        # Old Logic: Image Search logic -> Render 
        # New Logic: Init Picker -> Send Menu
        
        refined_title = final_title # Already refined by Gemini or Custom
        date_str = ctx_data.get('date_str', 'Latest') if ctx_data else 'Latest'
        
        # Save params for final render
        context.user_data['pending_render_params'] = {
            'title': refined_title,
            'summary': final_sub,
            'style_name': style_name,
            'date_str': date_str,
            # We don't save everything, just what's needed for render
        }
        
        # Initialize Picker
        picker = image_picker.ImagePicker(refined_title)
        context.user_data['image_picker'] = picker
        
        # Start Selection Flow
        await send_image_selection_menu(update, context)
        return


    elif data.startswith('img_pick_'):
        idx = int(data.split('_')[-1])
        picker = context.user_data.get('image_picker')
        
        if not picker:
             await query.message.reply_text("❌ Session expired. Please start over.")
             return

        # Use Global retrieval
        selected_url = picker.get_image_at_index(idx)
        
        # DEBUG: Log selection
        logger.info(f"User picked image global index {idx}. URL found: {bool(selected_url)}")
        
        if selected_url:
            await query.message.reply_text(f"✅ Selected Option {idx+1}. Rendering...")
            await perform_final_render(update, context, image_url=selected_url)
        else:
            await query.message.reply_text("❌ Invalid selection or image not found.")

    elif data == 'img_more':
        await send_image_selection_menu(update, context)

    elif data == 'img_skip':
        await query.message.reply_text("⏩ Skipping selection... AI will choose.")
        await perform_final_render(update, context, auto_search=True)

    elif data.startswith('unit_'):
        unit = data.replace('unit_', '')
        if unit in ['major', 'india']:
            db.update_user_unit(user_id, unit)
            await query.edit_message_text(text=f"✅ Unit updated to: {unit.capitalize()}\nYou will receive updates every 15 minutes.")
            context.user_data['waiting_for_city'] = False
            
    else:
        logger.warning(f"Unhandled callback data in main button handler: {data}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # 1. URL handling
    # 1. URL handling
    if text.lower().startswith('http') or text.lower().startswith('www'):
        
        # Check for Instagram
        from src.instagram_handler import InstagramHandler
        if InstagramHandler.is_instagram_url(text):
            status_msg = await update.message.reply_text("🔎 Analyzing Instagram Link...")
            
            # Process using Handler
            data = InstagramHandler.process_url(text)
            
            if not data:
                 await safe_edit_text(status_msg, "❌ Failed to download/process Instagram link.")
                 return
                 
            # 1. Video Reel
            if data['type'] == 'video' or data['type'] == 'REEL': # handler might return different strings
                 await safe_edit_text(status_msg, "🎬 Analyzing Reel...")
                 video_path = data['path']
                 
                 # Prepare content
                 title = data['caption'] or "Instagram Reel"
                 refined_title = gemini_utils.refine_headline(title)
                 summary = "Social Update" # Could generate from caption context
                 if data['caption']:
                     summary = gemini_utils.clean_text(gemini_utils.generate_one_liner(refined_title, data['caption']))
                 
                 await safe_edit_text(status_msg, "🎬 Rendering Video...")
                 overlay_io = image_generator.create_overlay_image(refined_title, summary, data['date'])
                 
                 if overlay_io:
                    final_path = video_generator.process_video_with_overlay(video_path, overlay_io)
                    if final_path:
                        await status_msg.delete()
                        await update.message.reply_video(
                            video=open(final_path, 'rb'), 
                            caption=f"🎥 **{refined_title}**\n_{summary}_"
                        )
                    else:
                        await status_msg.edit_text("❌ Video rendering failed.")
                 else:
                    await status_msg.edit_text("❌ Overlay failed.")
                    
            # 2. Image/Text Post
            elif data['type'] == 'image' or data['type'] == 'POST' or data['type'] == 'post_text':
                 caption = data['caption']
                 
                 if not caption:
                      await safe_edit_text(status_msg, "❌ No text found in post to generate content.")
                      return

                 await safe_edit_text(status_msg, "🧠 Generating Variations...")
                 
                 # Treat as manual text input -> Trigger Style Selection Flow
                 # Logic copied from 'img_' callback logic but adapted for direct trigger
                 
                 title = caption
                 context_text = caption
                 date_str = data.get('date', "Latest News")
                 
                 # Generate Variations
                 variations = gemini_utils.generate_all_variations(title[:200], context_text)
                 
                 if not variations or not isinstance(variations, dict):
                    await safe_edit_text(status_msg, "❌ Failed to generate styles.")
                    return

                 # Save context
                 context.user_data['img_gen_context'] = {
                    'variations': variations,
                    'date_str': date_str,
                    'original_title': title[:100] # Fallback for Custom
                 }
                 
                 # Preview Message
                 preview_text = "✨ **Choose a Style:**\n\n"
                 styles_map = ['Professional', 'Narrative', 'Simple', 'Casual']
                 for i, style in enumerate(styles_map):
                    var = variations.get(style, {})
                    h = var.get('headline', 'N/A')
                    s = var.get('sub', 'N/A')
                    preview_text += f"{i+1}. **{style}**\n   H: _{h}_\n   S: _{s}_\n\n"
                    
                 preview_text += "Or custom input?"
                 
                 keyboard = [
                    [InlineKeyboardButton("1. Pro", callback_data='var_Professional'), InlineKeyboardButton("2. Narrative", callback_data='var_Narrative')],
                    [InlineKeyboardButton("3. Simple", callback_data='var_Simple'), InlineKeyboardButton("4. Casual", callback_data='var_Casual')],
                    [InlineKeyboardButton("✍️ Custom", callback_data='style_custom')]
                 ]
                 
                 await status_msg.delete()
                 await update.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
                 return

        # YouTube Shorts (Legacy / Other Video)
        if 'youtube.com/shorts' in text.lower():
            status_msg = await update.message.reply_text("🎬 Downloading Shorts...")
            video_path = video_fetcher.download_video(text)
            
            if video_path:
                 # ... (Existing YT Logic) ...
                 await safe_edit_text(status_msg, "🔎 Analyzing video...")
                 item = fetcher.scrape_url_metadata(text)
                 title = item['title'] if item else "Video Update"
                 refined_title = gemini_utils.refine_headline(title)
                 date_str = item['published'] if item else "Latest"
                 summary = "Video Update"
                 
                 await safe_edit_text(status_msg, "🎬 Rendering...")
                 overlay_io = image_generator.create_overlay_image(refined_title, summary, date_str)
                 
                 if overlay_io:
                    final_path = video_generator.process_video_with_overlay(video_path, overlay_io)
                    if final_path:
                        await status_msg.delete()
                        await update.message.reply_video(video=open(final_path, 'rb'), caption=f"🎥 **{refined_title}**")
                    else:
                        await status_msg.edit_text("❌ Render failed.")
                 else:
                    await status_msg.edit_text("❌ Overlay failed.")
            else:
                 await status_msg.edit_text("❌ Download failed.")
            return
            
        status_msg = await update.message.reply_text("🔗 Analyzing link...")
        
        # Scrape
        item = fetcher.scrape_url_metadata(text)
        
        if item:
            context.user_data['last_scraped_item'] = item # Save for Context
            await status_msg.delete()
            summary_part = f"\n\n_{item.get('summary', '')}_" if item.get('summary') else ""
            msg = f"*{item['title']}*{summary_part}\n\n{item['published']}\n[Read more]({item['link']})"
            keyboard = [[InlineKeyboardButton("✨ Generate Copy", callback_data='copy_trigger')],
                        [InlineKeyboardButton("🎨 Generate Image", callback_data='img_trigger')]]
            
            await update.message.reply_text(
                text=msg, 
                parse_mode='Markdown', 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await status_msg.edit_text("❌ Could not extract news details from this link.")
        return

    # 2. City handling
    if context.user_data.get('waiting_for_city'):
        city_name = text
        unit = f"city_{city_name}"
        db.update_user_unit(user_id, unit)
        context.user_data['waiting_for_city'] = False
        await update.message.reply_text(f"✅ Unit updated to: {city_name.capitalize()}\nYou will receive updates every 15 minutes.")

async def scheduled_news_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running scheduled news job...")
    users = db.get_all_users()
    if not users: return

    # Filter out users who haven't selected a unit yet
    active_users = [u for u in users if u['unit'] and u['unit'] != 'none']
    if not active_users:
        logger.info("No active users with selected units.")
        return

    unique_units = set(u['unit'] for u in active_users)
    news_cache = {}
    
    for unit in unique_units:
        try:
            items = fetcher.fetch_news_for_unit(unit)
            if items: news_cache[unit] = items
        except Exception as e:
            logger.error(f"Error fetching for {unit}: {e}")
            
    for user in active_users:
        unit = user['unit']
        items = news_cache.get(unit, [])
        if not items: continue
        
        for item in items:
            summary_part = f"\n\n_{item.get('summary', '')}_" if item.get('summary') else ""
            msg = f"*{item['title']}*{summary_part}\n\n{item['published']}\n[Read more]({item['link']})"
            keyboard = [[InlineKeyboardButton("✨ Generate Copy", callback_data='copy_trigger')],
                        [InlineKeyboardButton("🎨 Generate Image", callback_data='img_trigger')]]
            try:
                await context.bot.send_message(chat_id=user['user_id'], text=msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
                db.mark_news_as_seen(item['link'])
            except Exception as e:
                logger.error(f"Failed to send to {user['user_id']}: {e}")
                
    # Cleanup
    db.cleanup_seen_news(days=3)

# --- Main Application ---
def run_bot():
    # Initialize DB
    db.init_db()
    
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("TELEGRAM_TOKEN is not set. Please check src/config.py.")
        return

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Create Conversation Handler
    create_conv = ConversationHandler(
        entry_points=[CommandHandler("create", start_create)],
        states={
            CREATE_IMG: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.TEXT & ~filters.COMMAND, create_handle_image)],
            CREATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_handle_title)],
            CREATE_SUB: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_handle_sub)],
            CREATE_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_handle_color)],
        },
        fallbacks=[CommandHandler("cancel", cancel_create)]
    )

    # Handlers
    from src.onboarding import onboarding_conv_handler
    application.add_handler(onboarding_conv_handler)
    
    application.add_handler(create_conv)
    application.add_handler(edit_conv_handler)
    
    # Commands
    application.add_handler(CommandHandler("reset", reset_bot))
    application.add_handler(CommandHandler("start_news", start_news))
    application.add_handler(CommandHandler("stop_news", stop_news))
    application.add_handler(CommandHandler("update", update_news_command))
    
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    
    # Job Queue
    job_queue = application.job_queue
    # 15 minutes = 900 seconds
    job_queue.run_repeating(scheduled_news_job, interval=900, first=10)
    
    logger.info("Bot is running...")
    application.run_polling()
