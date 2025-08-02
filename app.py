import eventlet
eventlet.monkey_patch()

import os
import json
import smtplib
import importlib
from datetime import datetime, date
from collections import defaultdict
from email.message import EmailMessage

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, join_room
from sqlalchemy import create_engine, text

# --- App Configuration ---
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a-strong-fallback-secret-key-for-local-development")
socketio = SocketIO(app, async_mode='eventlet')

# --- KNOWLEDGE BASE ---
# The text from the "New Beginnings" book
KNOWLEDGE_BASE = """
Hemorrhoids: Hemorrhoids are swollen veins at the opening of the rectum, inside the rectum, or outside of the anus. They can be painful, itchy, and even bleed. Although they’re usually not serious, they can be really uncomfortable. What can help: eat health (especially high-fiber) foods, drink plenty of water to avoid constipation, avoid straining during bowel movement, avoid sitting or standing for long periods of time, use pre-moistened wipes instead of toilet paper, apply ice packs or witch hazel pads to the hemorrhoids, soak in a warm tub several times a day, use topical creams, suppositories, and pain medication with your health care provider’s approval. 
Perineum: The perineum is the area between your vagina and rectum. During a vaginal birth, it stretches and may tear. So, you may have tears and lacerations in your perineum. These tears, along with any vaginal tears, can cause pain and tenderness for several weeks. During the first 24-48 hours, icing can help discomfort. Keeping the area clean and dry can help relieve pain, prevent infection, and promote healing.
Vaginal discharge: After giving birth, you can expect to have a bloody vaginal discharge, called lochia, for a few days. This is part of the natural healing process for your uterus. For the first few days, lochia is bright red, heavy in flow, and may have small blood clots. It has a distinct smell that women often describe as fleshy, musty, or earthy. Because blood collects in your vagina when you’re sitting or lying down, this may make lochia heavier when you stand up. You may notice a heavier blood flow after too much physical activity. If you do, you should slow down and rest. You may have less lochia if you had a cesarean birth. Over time, the flow gets less and lighter in color. But expect to have this lighter discharge for up to 4-6 weeks. You’ll want to use pads (not tampons or menstrual cups) until your lochia stops. Tampons or menstrual cups can increase the chance for infection in your uterus. First 1-3 days: bright to dark red, heavy to medium flow, may have small clots About days 3-10: pink or brown-tinged, medium to light flow, very few or no small clots About days 10-14 (maybe longer): yellowish-white color, very light flow, no clots or bright red color. Warning: Tell a nurse or call your health care provider immediately if you: soak through more than 1 pad in an hour, have a steady flow that continues over time, pass clots the size of an egg or larger after the first hour, have bright red vaginal bleeding day 4 or after, notice your lochia has a bad odor, have a fever of 100.4 degrees F or higher or 96.8 degrees F or lower, have severe pain in your lower abdomen.
Cesarean Birth Incision Care: If you had a cesarean birth, your incision may be closed with staples, stitches, wound closure strips, or surgical glue covered by a sterile dressing. Your outer dressing may be removed before you leave the hospital or during a follow-up visit with your provider. Wound closure strips come loose on their own after 7-10 days and then you can remove them. You may want to use a clean gauze over your incision, especially if the skin on your belly folds over it. Remember to always wash your hands before and after touching your incision. It’s important to check your incision daily to make sure it’s not infected. Some people find it helpful to stand in front of a mirror or use a hand-held mirror to check. Each time you clean your incision, make sure to use a clean freshly washed cloth. Otherwise, you’re at risk for infection. Clean it by washing with warm water and soap. Do not scrub it. Use a clean towel and gently pat dry. 
Moving After Cesarean Birth: When you get out of bed, roll to your side and use your top arm to push yourself up. Sit on the side of the bed for a minute before you get up to make sure you’re not dizzy. Place a pillow over your incision while you cough or move around in bed. If you have stairs at home, try to limit the number of times you go up and down them. Warning: Call your health care provider immediately if your incision is: red, separated, swollen, warm to touch, tender or painful, draining, not healing. Baby Blues: About 70-80% of new parents experience some negative feelings or mood swings that can start a few days after birth. “Baby blues” are common and usually last from a few days up to a few weeks. These feelings are likely related to changing hormones and fatigue. Common symptoms of baby blues can include: Weepiness, impatience, irritability, restlessness, anxiety, feeling tired, insomnia, sadness, mood changes, poor concentration. If you or your family feels your symptoms are more severe or have lasted longer than 2 weeks, contact your health care provider. There are plenty of treatment options if you need some help getting back on your feet. Tips: Don’t skimp on sleep and rest when you can, get out in nature and soak up some sunshine, get moving-walk or dance to your favorite music, keep doing the things you love, carve out time for your partner or a support person, reach out for peer support-in your community or online, make up your mind to meditate or journal, make time just for you-try a bath, aromatherapy, or massage. Postpartum Depression And Anxiety: About 1 in 7 new parents will experience moderate to severe symptoms of depression or anxiety after the birth of their baby. Symptoms of maternal postpartum depression can happen any time during the first year. Many of the symptoms are similar to the baby blues. The difference is that symptoms of postpartum depression and anxiety may: be felt more intensely, last most of the day, happen on more days than not, make it hard to function, affect your ability to care for your baby, change your feelings toward your baby. 

Family Pets: Because safety is a top priority, never leave your baby and pets alone together without an adult present.
Cats: When you bring your baby home, go to a quiet room and sit the baby on your lap. Let your cat come close when it’s ready.
Dogs: If your dog is well-trained, it will be easier to control their introduction and behavior around the new baby. If your dog will be allowed in the baby’s room, put a dog bed in the corner and give your dog a treat or toy for staying in the bed. If the baby’s room will be off limits, install a tall baby gate and place a dog bed outside the room.  When you bring your baby home, it’s important to warmly greet your dog without the baby in the room. After you’ve been home for a few hours, have a helper bring in your dog on a leash while you hold the baby. Talk in a calm and happy voice. If your dog is not stressed, let him briefly sniff the baby’s feet. Reward your dog for good behavior and repeat. 
Siblings: It’s normal for brothers or sisters to worry that the new baby will replace them or you will love the baby more. Encourage children to be honest about any feelings of jealousy, fear, or anger. To help them adjust, you can read books or watch videos with them about adding a baby to the family. Let children help with baby planning, shopping, and nursery decorations. Make sure to spend quality time with each child doing activities they enjoy. If siblings want to help care for their new baby brother or sister, it’s a good idea for you or another adult to supervise these interactions. 
Skin to Skin Contact: The connection of your bare-skinned baby lying directly on your skin is called skin to skin contact. This immediate undisturbed skin to skin contact allows your baby to go through instinctive stages. These include looking at you, resting and finally self-attachment to the breast. This initial snuggling also has very important health benefits. Benefits: Soothes and calms you and your baby, your baby cries less, helps your baby regulate their temperature and heart rate, helps your baby regulate their breathing and blood sugar, enhances bonding, helps your uterus shrink back to regular size. Safe positioning for safe skin to skin contact: you should be semi-reclined or upright and alert, your baby is in the middle and high up on your chest, your baby’s shoulders and chest are facing you, your baby’s head is turned to one side with mouth and nose visible, your baby’s chin is in a neutral position (not slouched)- also called sniffing position, your baby’s neck is straight, not bent, your baby’s arms and legs are flexed-in tight to the side of their body, your baby’s back is covered with warm blankets. Remember: Babies should always maintain good skin color. They should respond to stimulation. Babies are usually calm and relaxed during skin to skin contact. You may get sleepy as well. It’s best to have an alert adult in the room or nearby to help out. 
Newborn Appearance: 
Skin: Newborn babies can have a variety of harmless skin blemishes and rashes. A common condition is newborn acne, caused by your hormones. It will get better in the first few weeks. Your baby’s skin may be dry and peeling-mostly on the feet, hands, and scalp. This is simply the shedding of dead skin, and it will resolve on its own. The amount of time it takes to shed the outer layer of skin varies from baby to baby. 
Swollen Breasts and Genitals: After birth, both male and female babies’ breasts and genitals may look a little swollen. Their breasts may also secrete a small amount of fluid. You may find a small amount of blood-tinged vaginal discharge in your baby girl’s diaper. This is all normal and happens as the last of your pregnancy hormones circulate through the baby’s bloodstream. Within a few days after the birth, any breast and genital swelling and fluid discharge should stop. 
Head Shape: The plates of your baby’s skull bones aren’t fused together at birth. This allows the baby’s head to change shape as it moves through the birth canal and the baby’s brain to grow after birth. So, your baby’s head will probably look egg-shaped, pointed, or flattened at birth. There are 2 soft spots on your baby’s head-on top and in the back -where the skull bones haven’t fused. They’re called fontanelles. They’ll close and fuse permanently as the baby grows. 
Eyes: Newborns can be very alert. Even though they can only see 8-10 inches away, they may turn their heads toward different sounds. A baby’s eyes may be gray-blue or brown at birth. Babies with dark skin are usually born with dark eyes. You won’t know their final eye color for 6-12 months. Don’t worry if your baby’s eyes occasionally cross. This is normal and should stop in 3-4 months. Red spots in the whites of your baby’s eyes are also normal and will disappear in 1-2 weeks. 
Newborn Screenings: Newborn screenings are done shortly after birth to test for medical conditions that may not be detected during a physical examination. 
Hearing screening: Of every 1,000 babies born, it’s estimated that 1 to 3 will have serious hearing loss. It’s now standard practice to conduct hearing screening for newborns. If hearing loss in not caught early on, the hearing center in your baby’s brain won’t get enough stimulation. This can delay speech and other development in your newborn. 
Jaundice: Jaundice is common in newborn babies, giving their skin and the whites of their eyes a yellow color. It is typically caused by a buildup of a substance called ‘bilirubin’ in the baby’s blood and skin. The baby’s bilirubin level may be tested in one of two ways: By a light meter placed on your baby’s skin that calculates the bilirubin level. By a blood sample taken from their heel that will measure the level of bilirubin in their blood serum. If the level is high after the light meter testing, a blood test may be done to confirm the level. Treatment: Jaundice is typically resolved with treatment. There are 2 types of treatment for jaundice. Phototherapy involves placing your baby under a special light wearing only a diaper and eye protection. Another treatment involves placing a fiberoptic blanket under your baby. Sometimes, the light and blanket are used together. 
Umbilical cord: Your baby’s umbilical cord will look shiny and yellow immediately after birth. As it dries out, it may appear brown, gray or even purplish-blue. Before it shrinks and falls off, the cord will darken like the color of a scab on your skin. If the area around the umbilical cord looks red, is draining any type of fluid, smells bad, or has not fallen off by the third week of life, talk to your baby’s health care provider. Always wash your hands before touching the umbilical cord. Don’t put any type of ointment, creams, or bandage on the cord. If the baby’s bowel movement gets on the cord, wash with warm water and pat dry. 
Nail care: A baby’s nails are very soft and flexible. But because they don’t have a lot of control over their body movements, they can still scratch their own face. That’s why it’s best to trim or file your baby’s fingernails 1-2 times a week and toenails about every 2 weeks. 
Diaper Rash: Diaper rash is usually not a serious problem and will often improve in 3-4 days with simple treatment. But if it is not treated, diaper rash can become painful, causing bumps, blisters or sores. Diaper rash can even cause a more serious bacterial skin infection or yeast infection. Change baby’s diaper frequently during the day-about every 1 to 3 hours. Wash diaper area with water, then pat dry with a soft cloth. If you see redness, apply a thick layer of non-scented petroleum jelly or zinc-based diaper cream. Keep using jelly or cream with every diaper change until the redness disappears. Give your baby some time without a diaper to increase air flow and help heal the rash. 
Baby’s Behavior: Some babies are quiet by nature-they can remain still and content for a long time. They tend to move in a smooth and relaxed style. Other babies are more active and seem to be in constant motion. They’re excited and interested in looking around. These babies will be harder to settle, but swaddling and physical contact may help them calm down. Fussing or Crying: If your baby is wiggling or squirming, it’s a sign they may feel fussy. Fussiness may be followed by more vigorous movement of their arms and legs. And fussing may turn into crying as your baby tries to make their needs known. When your baby is crying, here are the questions to ask: Is my baby hungry or wants to suck? Gently settle your baby and feed them. Sucking on a finger, thumb, or breast may help. Do I need to change the diaper? Change diaper- some babies fuss when they are about to soil their diaper or when it needs to be changed. Does my baby want to be held? Try gentle pats to the back, rocking, or walking. Make a “shush” sound in your baby’s ear over and over. Is my baby cold or hot? Add a layer of clothing-babies need 1 more layer than adults. Remove a layer of clothing-your baby might also be hot. Is my baby lonely? Go outside-a change of scenery can be distracting. Give them a massage-the stroke can be soothing. 
Crying helps your baby release tension and shut out any sights, sounds, or sensations that may be overwhelming. Respond quickly to your newborn baby when they cry. When you consistently respond to your baby cries, they feel safe and secure. It also teaches them to trust you’ll be there to care for them. Do your best to meet the needs of your baby. 
Colic: Babies with colic have periods of frequent, long, and intense crying or fussiness-but are otherwise well-fed and healthy. Colic can be very frustrating and stressful for the parents, especially when there’s no obvious reason for their baby to be upset. And no amount of soothing seems to help. Even worse, episodes of colic often happen in the evening or at night when parents are tired and need sleep. Experts don’t know exactly what causes colic. But their “colicky” episodes usually peak when the bay is about 6 weeks old and start to taper off when the baby is 3-4 months old. There may be times when nothing you do will stop the crying. This is normal. If you’ve met the baby’s basic needs: clean diaper, fed, gently rocked, etc., then try these tips: take a deep breath and count to 10, put your baby in their crib and go to another room, ask a friend or family member to take over for awhile.
Safe Sleep: Alone: your baby should sleep alone, not with other people, pillows, blankets or stuffed animals. Back: Your baby should always be placed on their back, not their side or stomach. In their Crib: Your baby should sleep in a crib, not on an adult bed, sofa, cushion or other soft surface. Tips: Always place your baby on their back to sleep and nap, use a firm and flat (not inclined) sleep surface, like a mattress in a safety-approved crib, play yard, or other flat surfaced covered by a fitted sheet, when your baby falls asleep in their car seat, stroller, swing, infant carrier or sling, move them to a firm, flat sleep surface as soon as possible, keep all soft objects (pillows, blankets, toys, bumper pads, etc) out of the crib, dress your baby in a well-fitting, one piece sleeper, keep your baby’s head and face uncovered during sleep, keep your baby warm with a wearable (not loose) blanket, keep the room temperature comfortable and dress your baby in one more layer than you would wear. What not to do: don’t smoke or allow others to smoke around your baby, don’t drink alcohol  or use drugs around your baby, don’t use commercial devices or cardiorespiratory monitors unless ordered by your baby’s doctor, don’t use items with loose ties on or around a sleeping baby, including bibs, pacifiers, cords, and other attachments, don’t use products claiming to reduce risk or prevent SIDS, including wedges, positioners, or other products designed to keep infants in a specific position, don’t place electrical cords, window blind cords, or baby monitor cords close to the crib. 
Car Seats: All infants and toddlers should ride in a rear-facing car safety seat as long as possible, until they reach the highest weight or height allowed by the seat’s manufacturer. Most convertible seats allow children to ride rear-facing for 2 or more years. Because their spine is still developing and their head is large compared to the rest of their body, your new baby is at high risk for injury in a car crash. The safest place for your baby, is securely strapped into a rear-facing car seat. These seats cradle their head, neck, and spine. So, they’re protected if the car is involved in a frontal crash-the most common type of car crash. The “best” car safety seat is the one that fits your baby and is installed correctly in your car. It doesn’t matter, whether it’s the most expensive car seat made-if it’s not installed properly, it may not protect your baby. Did you know? Every car seat has an expiration date. As a car seat ages, the materials may become brittle and break. Check for information on your car seat with the model name, model number, date of manufacture and expiration date. And make sure you register your car seat with the manufacturer. That way you’ll be notified about any recalls. Tips: Installing seat in car: tightly install car seat in a rear-facing position in the back seat of the car, car seat should not move more than 1 inch side to side, car seat should recline according to manufacturer’s instructions, if allowed in your car, place car seat in the center position of the back seat. Warning: Look before you lock: Your car heats up faster and gets hotter than you might think. Remember to “look before you lock”, so you never forget your baby is with you. Never leave your child alone in the car, not even for one minute. Children’s body temperatures heat up to 3-5 times faster than adults.
Cluster Feeding: Cluster feeding is when your baby feeds close together at certain times of the day. And it’s very common in newborns. It  usually happens in the evening, but each baby is different. You’ll generally see 5-10 feedings over a 2-3 hour period, followed by 4-5 hours of deep sleep. Tips: Because all of these feedings may work your body overtimes, here are some tips to remember: make sure you’re eating and drinking, make yourself a “nest” for the day and make sleep a priority, talk to other moms. Get the support you need, ask for help when you need it, let your baby breastfeed whenever they want to. 
Remember: If baby chooses to take only 1 breast at a feeding, make sure you start with the other breast at the next feeding. Alternating breasts will help with proper milk removal, Keep baby interested and awake during feedings. Following these steps will help to ensure regular milk removal, increase milk production, reduce breast engorgement and nipple tenderness, and maximize infant weight gain. 
Burping: After feeding, try to burp your baby. Not all babies will burp in the first few days after birth. To burp, pat the baby’s back gently or stroke the back with an upward motion. If your baby doesn’t burp after a few minutes, resume the feeding. 
Feeding your baby a bottle: Feeding time presents an ideal opportunity for you to bond with your newborn. It’s a special time to build a strong foundation for the rest of your baby’s life. How do I know my baby’s ready to eat? When your baby’s ready to eat, they have ways of letting you know. They’ll start by showing feeding cues. Feedings usually go more smoothly if you start when they’re showing early cues. Practicing rooming in and placing your baby skin to skin can help you learn their cues. You’ll be right there where you can respond to them quickly. If your baby is already crying, they may be too upset to feed. When this happens, calm your baby first by gently rocking them side to side or through skin to skin contact. What do my baby’s feeding cues look like? Head moving side to side, hands to mouth and stretching, lips smacking and puckering, tongue sticking out and fidgeting. What are proper bottle feeding techniques? Your baby will learn to suck, swallow and breathe-all at the same time. As new parents who are bottle feeding, you’ll learn the techniques that are best for your baby, and for yourselves. So, try to keep an open mind as your share this learning experience with your little one. A newborn needs human contact. Feeding is an ideal time to share it. Take advantage of this time to make eye contact with your baby and to really connect. Make this a time to touch, talk and sing. Try not to get distracted by your phone or other electronic devices. A baby also benefits from skin to skin time with parents during feedings. If you’re comfortable and relaxed, your baby will be too. Is there more than one way to bottlefeed? In traditional method, you cradle your baby securely in the crook of your arm as you hold the bottle in your other hand. Then when your baby is ready, gradually tip the bottle up. You want the fluid to fill the nipple, but you don’t want to let any air enter it. If you’re comfortable with this method, then you can stick with it. You may also try a more natural method called paced bottle feeding. This style lets the baby set the pace, eat more slowly, and take breaks as needed. In this method, you hold the bottle horizontally and hold the baby more upright. When  you notice your baby pausing between bursts of sucking, remove the nipple from your baby’s mouth. Then allow the nipple to rest on your baby’s lip until the baby starts sucking again. In paced bottle feeding, the baby controls the flow of milk. This methods helps prevent both overfeeding and choking. How to pace bottle feed: hold your baby in an upright position, supporting their head and neck with your arm or hand, use the nipple to touch your baby’s upper lip. Encourage baby to open their mouth wide. Let your baby pull the nipple into their mouth, don’t force them to take it. Keep nipple horizontal so the nipple remains partially full. This will slow the flow of the milk. Give your baby breaks and watch for signs they are ready to end the feeding. If your baby is drinking too fast, tip the bottle down or remove it slow the pace. If your baby spits up after you feed them: try giving them less or try smaller amounts more frequently. Try burping them several times during the feeding. Hold them upright for 15-30 minutes after a feeding. Avoid bouncing them or active play right after a feeding . Avoid placing them on their tummy right after a feeding. Warning: Contact your health care provider if your baby: vomits 1/3 or more of their formula at most feeding sessions, projectile vomits-or forcefully spews out the contents of their stomach. Burping your baby: After feeding, it’s time to try to burp your baby. During the first few days after birth, not all babies will burp. So, just do your best. To burp your baby, gently pat them on the back or stroke their back with an upward motion. If your baby doesn’t burp after a few minutes, you can keep feeding. Try burping a few more times during the feeding when the sucking slows down or stops. How do I know when my baby has finished feeding? You want to make sure you don’t overfeed your baby. Just like they show cues when they’re hungry, your baby also has ways of letting you know they’re ready to end the feeding. So watch and listen closely to your baby throughout the feeding. Watch for these cues: closes mouth, turns head away, relaxes hands, no longer sucking, letting go of the nipple. Warning: Stop the feeding if the following signs of stress occur: turning the head, arching the back, choking, sputtering, changing color, moving the arms, tensing fists while eating. 
How do I know if formula isn’t agreeing with my baby? Most healthy baby cry, fuss, get gassy and spit up from time to time. Only a very small percentage of babies actually have a formula intolerance and need to change formula type. There are signs that your baby may be allergic to the formula you are feeding them. These signs include excessive crying or fussiness after a feeding, very gassy, very watery stools or forceful vomiting. Their skin could also be red and scaly. Is it normal for my baby to spit up after feeding? Most babies spit up because the muscle around the opening of the stomach isn’t strong enough to keep the milk or formula down. Spitting up will usually go aways as babies develop more and can sit up. It is possible that spitting up a lot is a sign of acid reflux, an allergy or intolerance of the formula. 
Bottle Feeding Don’ts: never leave your baby alone, never prop a bottle in place, never put baby to bed with a bottle, never add baby cereal in the bottle. 

"""

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("WARNING: DATABASE_URL environment variable not found. Using a local SQLite database.")
    DATABASE_URL = "sqlite:///local_call_light.db"

engine = create_engine(DATABASE_URL)

# --- Database Setup ---
def setup_database():
    try:
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS requests (
                    id SERIAL PRIMARY KEY,
                    request_id VARCHAR(255) UNIQUE,
                    timestamp TIMESTAMP WITHOUT TIME ZONE,
                    completion_timestamp TIMESTAMP WITHOUT TIME ZONE,
                    room VARCHAR(255),
                    user_input TEXT,
                    category VARCHAR(255),
                    reply TEXT,
                    is_first_baby BOOLEAN
                );
            """))
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS assignments (
                    id SERIAL PRIMARY KEY,
                    assignment_date DATE NOT NULL,
                    room_number VARCHAR(255) NOT NULL,
                    nurse_name VARCHAR(255) NOT NULL,
                    UNIQUE(assignment_date, room_number)
                );
            """))
            connection.commit()
        print("Database setup complete. Tables are ready.")
    except Exception as e:
        print(f"CRITICAL ERROR during database setup: {e}")

# --- Core Helper Functions ---
def log_request_to_db(request_id, category, user_input, reply):
    room = session.get("room_number", "Unknown Room")
    is_first_baby = session.get("is_first_baby", None)
    try:
        with engine.connect() as connection:
            connection.execute(text("""
                INSERT INTO requests (request_id, timestamp, room, category, user_input, reply, is_first_baby)
                VALUES (:request_id, :timestamp, :room, :category, :user_input, :reply, :is_first_baby);
            """), {
                "request_id": request_id,
                "timestamp": datetime.now(),
                "room": room,
                "category": category,
                "user_input": user_input,
                "reply": reply,
                "is_first_baby": is_first_baby
            })
            connection.commit()
    except Exception as e:
        print(f"ERROR logging to database: {e}")

def send_email_alert(subject, body):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL", "call.light.project@gmail.com")
    if not sender_email or not sender_password:
        print("WARNING: Email credentials not set. Cannot send email.")
        return
    msg = EmailMessage()
    msg["Subject"] = f"Room {session.get('room_number', 'N/A')} - {subject}"
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
    except Exception as e:
        print(f"ERROR: Email failed to send: {e}")

def process_request(role, subject, user_input, reply_message):
    request_id = 'req_' + str(datetime.now().timestamp()).replace('.', '')
    
    socketio.start_background_task(send_email_alert, subject, user_input)
    socketio.start_background_task(log_request_to_db, request_id, role, user_input, reply_message)
    
    socketio.emit('new_request', {
        'id': request_id,
        'room': session.get('room_number', 'N/A'),
        'request': user_input,
        'role': role,
        'timestamp': datetime.now().isoformat()
    })
    return reply_message

def get_ai_response(question, context):
    question_lower = question.lower()
    
    nurse_keywords = ["pain", "dizzy", "bleeding", "headache", "nausea", "sad", "scared", "anxious", "crying", "help", "emergency", "harm"]
    if any(keyword in question_lower for keyword in nurse_keywords):
        return "NURSE_ACTION"

    topic_map = {
    "jaundice": "Jaundice:", "uterus": "Uterus:", "cramps": "Uterus:", "afterbirth": "Uterus:",
    "bladder": "Bladder:", "urinate": "Bladder:", "bowel": "Bowels:", "constipation": "Bowels:",
    "hemorrhoid": "Hemorrhoids:", "perineum": "Perineum:", "discharge": "Vaginal discharge:", "lochia": "Vaginal discharge:",
    "gas": "Gas Pains:", "incision": "Cesarean Birth Incision Care:", "cesarean": "Cesarean Birth Incision Care:",
    "moving": "Moving After Cesarean Birth:", "baby blues": "Baby Blues:", "depression": "Postpartum Depression And Anxiety:",
    "ocd": "Postpartum Obsessive-Compulsive Disorder (OCD):", "psychosis": "Postpartum Psychosis:",
    "family pets": "Family Pets:", "cat": "Cats:", "dog": "Dogs:",
    "siblings": "Siblings:", "brother": "Siblings:", "sister": "Siblings:",
    "skin to skin": "Skin to Skin Contact:", "acne": "Newborn Appearance:", "swollen": "Newborn Appearance:", "head shape": "Newborn Appearance:",
    "eyes": "Newborn Appearance:", "hearing": "Newborn Screenings:", "umbilical": "Umbilical cord:", "cord": "Umbilical cord:",
    "nail": "Nail care:", "rash": "Diaper Rash:", "diapering": "Diapering:", "meconium": "Diapering:", "stools": "Diapering:",
    "behavior": "Baby’s Behavior:", "crying": "Baby’s Behavior:", "fussing": "Baby’s Behavior:", "colic": "Colic:",
    "sleep": "Safe Sleep:", "sids": "Safe Sleep:", "car seat": "Car Seats:", "temperature": "Taking Baby’s Temperature:",
    "cluster feeding": "Cluster Feeding:", "burping": "Burping:", "bottle feeding": "Feeding your baby a bottle:"
}
    paragraphs = [p.strip() for p in context.strip().split('\n') if p.strip()]
    for keyword, title in topic_map.items():
        if keyword in question_lower:
            for p in paragraphs:
                if p.startswith(title):
                    return p

    cna_keywords = ["pillow", "water", "blanket", "ice", "pad", "diaper", "formula"]
    if any(keyword in question_lower for keyword in cna_keywords):
        return "CNA_ACTION"

    return "CANNOT_ANSWER"

# --- App Routes ---
@app.route("/room/<room_id>")
def set_room(room_id):
    session.clear()
    session["room_number"] = room_id
    session["pathway"] = "standard"
    return redirect(url_for("language_selector"))

@app.route("/bereavement/<room_id>")
def set_bereavement_room(room_id):
    session.clear()
    session["room_number"] = room_id
    session["pathway"] = "bereavement"
    return redirect(url_for("language_selector"))

@app.route("/", methods=["GET", "POST"])
def language_selector():
    if request.method == "POST":
        session["language"] = request.form.get("language")
        pathway = session.get("pathway", "standard")
        
        if pathway == "bereavement":
            session["is_first_baby"] = None
            return redirect(url_for("handle_chat"))
        else:
            return redirect(url_for("demographics"))
            
    return render_template("language.html")

@app.route("/demographics", methods=["GET", "POST"])
def demographics():
    lang = session.get("language", "en")
    config_module_name = f"button_config_{lang}"
    
    try:
        button_config = importlib.import_module(config_module_name)
        button_data = button_config.button_data
    except (ImportError, AttributeError):
        return "Error: Language configuration file is missing or invalid."

    if request.method == "POST":
        is_first_baby_response = request.form.get("is_first_baby")
        session["is_first_baby"] = True if is_first_baby_response == 'yes' else False
        return redirect(url_for("handle_chat"))

    question_text = button_data.get("demographic_question", "Is this your first baby?")
    yes_text = button_data.get("demographic_yes", "Yes")
    no_text = button_data.get("demographic_no", "No")
    
    return render_template("demographics.html", question_text=question_text, yes_text=yes_text, no_text=no_text)

@app.route("/chat", methods=["GET", "POST"])
def handle_chat():
    pathway = session.get("pathway", "standard")
    lang = session.get("language", "en")
    
    config_module_name = f"button_config_bereavement_{lang}" if pathway == "bereavement" else f"button_config_{lang}"
    
    try:
        button_config = importlib.import_module(config_module_name)
        button_data = button_config.button_data
    except (ImportError, AttributeError) as e:
        print(f"ERROR: Could not load configuration module '{config_module_name}'. Error: {e}")
        return f"Error: Configuration file '{config_module_name}.py' is missing or invalid. Please contact support."

    if request.method == 'POST':
        user_input = request.form.get("user_input", "").strip()
        
        if user_input == button_data.get("ai_yes"):
            original_question = session.get("last_ai_question", "A patient has a question.")
            reply = process_request(role="nurse", subject="Patient Follow-up Request", user_input=original_question, reply_message=button_data["nurse_notification"])
            return render_template("chat.html", reply=reply, options=button_data["main_buttons"], button_data=button_data)
        elif user_input == button_data.get("ai_no"):
            return redirect(url_for('handle_chat'))

        if request.form.get("action") == "send_note":
            note_text = request.form.get("custom_note")
            if note_text:
                ai_answer = get_ai_response(note_text, KNOWLEDGE_BASE)
                
                if ai_answer == "NURSE_ACTION":
                    reply = process_request(role="nurse", subject="Custom Patient Note (AI Triage)", user_input=note_text, reply_message=button_data["nurse_notification"])
                    options = button_data["main_buttons"]
                elif ai_answer == "CNA_ACTION":
                    reply = process_request(role="cna", subject="Custom Patient Note (AI Triage)", user_input=note_text, reply_message=button_data["cna_notification"])
                    options = button_data["main_buttons"]
                elif ai_answer == "CANNOT_ANSWER":
                    reply = process_request(role="nurse", subject="Custom Patient Note (AI Triage)", user_input=note_text, reply_message=button_data["nurse_notification"])
                    options = button_data["main_buttons"]
                else:
                    session["last_ai_question"] = note_text
                    reply = f"{ai_answer}\n\n{button_data.get('ai_follow_up_question', 'Would you like to speak to your nurse?')}"
                    options = [button_data.get("ai_yes", "Yes"), button_data.get("ai_no", "No")]
            else:
                reply = "Please type a message in the box."
                options = button_data["main_buttons"]
            return render_template("chat.html", reply=reply, options=options, button_data=button_data)
        
        if user_input == button_data.get("back_text", "⬅ Back"):
            return redirect(url_for('handle_chat'))

        if user_input in button_data:
            button_info = button_data[user_input]
            reply = button_info.get("question") or button_info.get("note", "")
            options = button_info.get("options", [])
            
            if button_info.get("follow_up"):
                session["last_ai_question"] = user_input
                reply = f"{reply}\n\n{button_data.get('ai_follow_up_question', 'Would you like to speak to your nurse?')}"
                options = [button_data.get("ai_yes", "Yes"), button_data.get("ai_no", "No")]
            else:
                back_text = button_data.get("back_text", "⬅ Back")
                if options and back_text not in options:
                    options.append(back_text)
                elif not options:
                    options = button_data["main_buttons"]

                if "action" in button_info:
                    action = button_info["action"]
                    role = "cna" if action == "Notify CNA" else "nurse"
                    subject = f"{role.upper()} Request"
                    notification_message = button_info.get("note", button_data[f"{role}_notification"])
                    reply = process_request(role=role, subject=subject, user_input=user_input, reply_message=notification_message)
                    options = button_data["main_buttons"]
        else:
            reply = "I'm sorry, I didn't understand that. Please use the buttons provided."
            options = button_data["main_buttons"]

        return render_template("chat.html", reply=reply, options=options, button_data=button_data)

    return render_template("chat.html", reply=button_data["greeting"], options=button_data["main_buttons"], button_data=button_data)

@app.route("/reset-language")
def reset_language():
    session.clear()
    return redirect(url_for("language_selector"))

@app.route("/dashboard")
def dashboard():
    active_requests = []
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT request_id, room, user_input, category as role, timestamp
                FROM requests 
                WHERE completion_timestamp IS NULL 
                ORDER BY timestamp DESC;
            """))
            for row in result:
                active_requests.append({
                    'id': row.request_id,
                    'room': row.room,
                    'request': row.user_input,
                    'role': row.role,
                    'timestamp': row.timestamp.isoformat()
                })
    except Exception as e:
        print(f"ERROR fetching active requests: {e}")
    
    return render_template("dashboard.html", active_requests=json.dumps(active_requests))

@app.route('/analytics')
def analytics():
    try:
        with engine.connect() as connection:
            top_requests_result = connection.execute(text("SELECT category, COUNT(id) FROM requests GROUP BY category ORDER BY COUNT(id) DESC;"))
            top_requests_data = top_requests_result.fetchall()
            top_requests_labels = [row[0] for row in top_requests_data]
            top_requests_values = [row[1] for row in top_requests_data]

            requests_by_hour_result = connection.execute(text("SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(id) FROM requests GROUP BY hour ORDER BY hour;"))
            requests_by_hour_data = requests_by_hour_result.fetchall()

            hourly_counts = defaultdict(int)
            for hour, count in requests_by_hour_data:
                hourly_counts[int(hour)] = count
            
            requests_by_hour_labels = [f"{h}:00" for h in range(24)]
            requests_by_hour_values = [hourly_counts[h] for h in range(24)]

    except Exception as e:
        print(f"ERROR fetching analytics data: {e}")
        top_requests_labels, top_requests_values = [], []
        requests_by_hour_labels, requests_by_hour_values = [], []

    return render_template('analytics.html', top_requests_labels=json.dumps(top_requests_labels), top_requests_values=json.dumps(top_requests_values), requests_by_hour_labels=json.dumps(requests_by_hour_labels), requests_by_hour_values=json.dumps(requests_by_hour_values))
    
@app.route('/assignments', methods=['GET', 'POST'])
def assignments():
    if request.method == 'POST':
        today = date.today()
        try:
            with engine.connect() as connection:
                with connection.begin():
                    for key, nurse_name in request.form.items():
                        if key.startswith('nurse_for_room_'):
                            room_number = key.replace('nurse_for_room_', '')
                            if nurse_name and nurse_name != 'unassigned':
                                connection.execute(text("""
                                    INSERT INTO assignments (assignment_date, room_number, nurse_name)
                                    VALUES (:date, :room, :nurse)
                                    ON CONFLICT (assignment_date, room_number)
                                    DO UPDATE SET nurse_name = EXCLUDED.nurse_name;
                                """), {"date": today, "room": room_number, "nurse": nurse_name})
                            else:
                                connection.execute(text("""
                                    DELETE FROM assignments 
                                    WHERE assignment_date = :date AND room_number = :room;
                                """), {"date": today, "room": room_number})
            print("Assignments saved successfully.")
        except Exception as e:
            print(f"ERROR saving assignments: {e}")
        return redirect(url_for('dashboard'))

    return render_template('assignments.html')

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)

@socketio.on('acknowledge_request')
def handle_acknowledge(data):
    room = data['room']
    message = data['message']
    socketio.emit('status_update', {'message': message}, to=room)

@socketio.on('defer_request')
def handle_defer_request(data):
    socketio.emit('request_deferred', data)

@socketio.on('complete_request')
def handle_complete_request(data):
    request_id = data.get('request_id')
    if request_id:
        try:
            with engine.connect() as connection:
                connection.execute(text("""
                    UPDATE requests 
                    SET completion_timestamp = :now 
                    WHERE request_id = :request_id;
                """), {"now": datetime.now(), "request_id": request_id})
                connection.commit()
            print(f"Request {request_id} marked as complete.")
        except Exception as e:
            print(f"ERROR updating completion timestamp: {e}")

with app.app_context():
    setup_database()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, use_reloader=False)

