from sekai_translator.core_client import SekaiCoreClient

core = SekaiCoreClient(
    core_path=r"C:\Users\lucas\Documents\Sekai Visual Novel\Ferramentas\SekaiTranslatorV\sekai-core\target\debug\sekai-core.exe"
)

core.start()

print(core.send("ping"))

resp = core.send(
    "parse_text",
    {
        "text": '<Yuki>"……本当に、来ると思わなかった。"\n今日は寒いね。'
    }
)

for e in resp["payload"]["entries"]:
    print(e)

core.stop()
