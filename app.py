from dotenv import load_dotenv

load_dotenv()

import auth  # noqa: E402
import data_layer  # noqa: E402

auth.setup()
data_layer.setup()

# Side-effect imports: register Chainlit callbacks via decorators
import ui.setup      # noqa: E402, F401  — on_settings_update
import ui.starters   # noqa: E402, F401  — set_starters
import ui.downloads  # noqa: E402, F401  — download_rapport, download_rapport_pdf, download_python
import ui.actions    # noqa: E402, F401  — followup, explore_question (also imports ui.chat)
