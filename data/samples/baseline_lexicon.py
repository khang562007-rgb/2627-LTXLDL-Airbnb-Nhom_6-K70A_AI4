# -*- coding: utf-8 -*-
"""Tài nguyên từ vựng cho src/baseline.py (phương pháp đối chứng, KHÔNG dùng LLM).

Quy ước: từ viết thường; hậu tố '*' = khớp tiền tố (vd 'perfect*' khớp 'perfectly').
Trọng số: pos2=+2 (khen mạnh), pos1=+1, neg1=-1, neg2=-2 (chê mạnh).
Danh sách do nhóm tự soạn (Câu 4C: phần 'từ khóa du lịch' tự viết); chưa nạp từ điển công bố bên ngoài.
Cố ý KHÔNG đưa vào các từ dễ gây nhiễu ở Porto như 'old'/'vieja'/'velho' (old town), 'laut' (de: theo mô tả).
"""

LANGS = ("en", "es", "fr", "de", "pt")

SENTIMENT = {
"en": dict(
 pos2="amazing awesome excellent fantastic perfect* wonderful superb outstanding spotless flawless incredible lovely gorgeous stunning brilliant exceptional impeccable love loved recommend*",
 pos1="good great nice clean comfortable comfy cozy cosy friendly helpful welcoming convenient quiet spacious beautiful charming pleasant enjoyed enjoy enjoyable satisfied responsive kind easy safe central close cute fresh tidy happy glad peaceful",
 neg1="bad poor noisy loud dark small tiny smelly smell smelled uncomfortable disappointed disappointing broken damaged cold humid damp stained cramped outdated unhelpful slow problem problems issue issues complaint* unfortunately lacking lack messy steep far expensive overpriced misleading inaccurate unresponsive annoying unclean thin",
 neg2="terrible awful horrible disgusting filthy worst dreadful unacceptable nightmare appalling scam rude unsafe dirty infested bedbug* cockroach* mold mould mouldy moldy"),
"es": dict(
 pos2="increíble increible excelente fantástic* fantastic* perfect* maravillos* espectacular* estupend* impecable genial magnífic* magnific* recomend* recomiend* encant* adoramos",
 pos1="buen* bonit* limpio limpia limpios limpias cómod* comod* amabl* agradabl* tranquil* céntric* centric* cerca espacios* acogedor* atento atenta atentos práctic* practic* bien bienvenid* feliz satisfech* disfrut* precioso preciosa preciosos preciosas lind* ordenad* silencios*",
 neg1="mal malo* mala* ruid* pequeñ* oscur* incómod* incomod* decepcion* roto* rota* frío frio húmed* humed* mancha* problema* queja* lento lenta lentos lentas caro caros carísimo falta lejos molest* engañ* descuidad*",
 neg2="horrible* terrible* pésim* pesim* asquer* suci* inaceptable estafa peor desastre* fatal infestad* cucaracha* chinche* moho"),
"fr": dict(
 pos2="excellent* parfait* super génial* genial* magnifique* fantastique* formidable* impeccable* exceptionnel* incroyable merveilleu* superbe* adoré* adore* adorable recommand* top idéal* ideal*",
 pos1="bon bonne bons bonnes bien agréable* agreable* propre propres confortable* accueillant* sympa* sympathique* calme* tranquille* spacieu* charmant* pratique* proche central* centrale réactif* reactif* disponible* aimable* gentil* joli* beau belle beaux belles heureu* satisfait* apprécié* apprecie* cosy lumineu*",
 neg1="mal mauvais* mauvaise* bruyant* bruit* minuscule* exigu* sombre* vieillot* inconfortable* déçu* decu* décevant* decevant* cassé* froid* humide* humidité humidite tache* problème* probleme* souci soucis plainte* lent lente lents lentes manque* loin mensonger* trompeur* désagréable* desagreable*",
 neg2="horrible* terrible* affreu* dégoûtant* degoutant* dégueu* sale sales saleté* salete* catastroph* pire arnaque* inacceptable cauchemar* infect* moisi* punaise* cafard* nul nulle nuls"),
"de": dict(
 pos2="ausgezeichnet* perfekt* fantastisch* wunderbar* wunderschön* wunderschon* super toll* hervorragend* großartig* grossartig* traumhaft* makellos* herrlich* genial* exzellent* empfehl* spitze top",
 pos1="gut* schön* sauber* bequem* freundlich* hilfsbereit* gemütlich* gemutlich* ruhig* zentral* geräumig* geraumig* praktisch* angenehm* nett* sympathisch* zufrieden* problemlos* unkompliziert* komfortabel* charmant* liebevoll* nah nahe bestens",
 neg1="schlecht* lärm* laerm* lärmend* hellhörig* hellhorig* dunkel* klein kleine kleiner kleines kleinen winzig* alt alte alten altes veraltet* muffig* unbequem* enttäusch* enttausch* kaputt* kalt* feucht* fleck* problem* beschwerde* langsam* teuer* mangel* weit unfreundlich* ungepflegt* irreführend* ärgerlich* störend* storend* stinkt gestunken",
 neg2="schrecklich* furchtbar* entsetzlich* ekelhaft* dreckig* schmutzig* katastroph* schlimm* unakzeptabel* abzocke* betrug lüge schimmel* wanzen kakerlake* widerlich* mies*"),
"pt": dict(
 pos2="excelente* perfeit* fantástic* fantastic* maravilhos* espetacular* impecável* impecavel* incrível* incrivel* ótim* otim* óptim* optim* magnífic* magnific* adorei adorámos adoramos adorável adoravel recomend* sensacional excecional excepcional top",
 pos1="bom boa bons boas bem bonito* bonita* limpo limpa limpos limpas confortável* confortavel* simpátic* simpatic* agradável* agradavel* tranquilo* tranquila* central perto próximo* proximo* espaçoso* espacoso* acolhedor* atencioso* prestável* prestavel prático* pratico* gentil feliz satisfeit* gostámos gostamos gostei aconchegante* cómodo* comodo* charmoso* lind*",
 neg1="mal mau maus má barulh* ruído* ruido* escuro* pequeno* pequena* desconfortável* desconfortavel* desiludid* dececion* decepcion* frio* húmido* humido* humidade mancha* problema* queixa* lento* lenta* caro caros falta* longe enganos* enganador* desagradável* desagradavel* incómod* incomod*",
 neg2="horrível* horrivel* terrível* terrivel* péssim* pessim* nojent* sujo* suja* inaceitável inaceitavel pior desastre* burla* fraude mofo bolor percevejo* infestad*"),
}

NEGATORS = {
 "en": "not no never cannot neither nor without nothing none hardly barely",
 "es": "no nunca jamás jamas ni tampoco sin nada ningún ninguno* ninguna*",
 "fr": "ne pas non jamais aucun* rien sans ni",
 "de": "nicht kein* nie niemals nichts ohne weder nirgends",
 "pt": "não nao nunca jamais nem sem nada nenhum* nenhuma*",
}

# Từ chuyển ý: chỉ dùng để ngắt mệnh đề (cửa sổ phủ định / khía cạnh không vượt qua).
CONTRAST = {
 "en": "but however although though yet whereas",
 "es": "pero aunque embargo sino",
 "fr": "mais cependant pourtant toutefois",
 "de": "aber jedoch allerdings obwohl doch sondern",
 "pt": "mas porém porem contudo embora",
}

# Từ dừng nhỏ cho bộ nhận diện ngôn ngữ dự phòng (khi không có fastText).
STOPWORDS = {
 "en": "the and was were very our had have this that with you are but",
 "es": "el los las y es una que con para muy nos por del pero estaba",
 "fr": "le les et est une que pour avec très nous du pas dans cette sont",
 "de": "der die das und ist war ein eine mit für sehr wir nicht auf von sind",
 "pt": "os as e é uma que com para muito nós do da foi não",
}

# Nhãn khía cạnh (tiếng Việt, khớp config) -> khóa nội bộ
ASPECT_KEYS = {
 "vị trí": "location", "sạch sẽ": "cleanliness", "chủ nhà": "host", "giá trị": "value",
 "tiện nghi": "amenities", "độ ồn": "noise", "an toàn": "safety", "dịch vụ": "service",
 "độ chính xác với mô tả listing": "listing_accuracy", "tổng thể trải nghiệm": "overall_experience",
}
DEFAULT_ASPECTS = list(ASPECT_KEYS.keys())

ASPECTS = {
"location": dict(
 en="location located neighbourhood neighborhood area central walking walk distance metro tram transport* situated position",
 es="ubicación ubicacion localización zona barrio céntric* centr* cerca lejos metro transporte* situad*",
 fr="emplacement situation situé* quartier localisation proche loin central* centre métro metro transport* adresse",
 de="lage standort gegend viertel zentral* zentrum nähe nahe entfernung bahn metro straßenbahn anbindung gelegen",
 pt="localização localizacao zona bairro central* centro perto longe metro metropolitano transportes* situad* localiza*"),
"cleanliness": dict(
 en="clean* dirt* dirty spotless tidy messy mess hygiene stain* smell* bedbug* cockroach* mold* mould* filth* unclean dust*",
 es="limpi* suci* higiene polvo olor* mancha* cucaracha* chinche* moho ordenad*",
 fr="propre* propreté sale sales saleté* ménage hygiène poussière odeur* tache* cafard* punaise* moisi* nettoy*",
 de="sauber* sauberkeit schmutz* dreck* hygiene staub* geruch* fleck* schimmel* kakerlake* wanzen putz*",
 pt="limp* sujo* suja sujidade higiene cheiro* mancha* mofo bolor percevejo* arrumad*"),
"host": dict(
 en="host hosts hosted hosting owner landlord",
 es="anfitri* propietari* dueñ* host",
 fr="hôte hôtes hote hotes propriétaire* proprietaire* host",
 de="gastgeber* vermieter* host eigentümer*",
 pt="anfitri* proprietári* proprietari* senhorio* host"),
"value": dict(
 en="value price* cost* worth money expensive cheap* affordable overpriced rate",
 es="precio* valor dinero caro* barato* económic* vale",
 fr="prix rapport tarif* argent cher chère économique* valeur coût",
 de="preis* leistung wert* geld teuer* günstig* billig* kosten*",
 pt="preço* preco* valor dinheiro caro* barato* económic* custo*"),
"amenities": dict(
 en="amenit* facilit* kitchen* bed beds bedroom* bathroom* shower* wifi internet conditioning aircon heating tv washer* towel* coffee furnish* equipped balcony terrace parking elevator lift stairs mattress* pillow*",
 es="comodidades cocina* cama* habitaci* baño* ducha* wifi internet aire acondicionado calefacci* tv lavadora toalla* equipad* balcón balcon terraza aparcamiento parking ascensor escalera* colchón colchon almohada*",
 fr="cuisine* lit lits chambre* bain douche* wifi internet climatisation chauffage télé tv lave* serviette* équip* balcon terrasse parking ascenseur escalier* matelas oreiller* literie",
 de="küche* bett* betten schlafzimmer* bad badezimmer* dusche* wlan wifi internet klimaanlage heizung fernseher tv waschmaschine handtuch handtücher ausgestattet* ausstattung balkon terrasse parkplatz aufzug fahrstuhl treppe* matratze* kissen",
 pt="comodidades cozinha* cama* quarto* banho duche* wifi internet ar condicionado aquecimento tv máquina toalha* equipad* varanda terraço estacionamento parking elevador escada* colchão almofada*"),
"noise": dict(
 en="noise* noisy loud quiet silent silence sound* traffic street party walls earplugs peaceful music neighbour* neighbor*",
 es="ruid* silenci* tranquil* calle tráfico trafico fiesta* paredes vecin* música musica",
 fr="bruit* bruyant* silenc* calme* tranquill* rue circulation fête* murs voisin* musique",
 de="lärm* ruhig* stille geräusch* verkehr straße strasse party hellhörig* wände nachbar* musik",
 pt="barulh* ruído* ruido* silêncio silencio* tranquil* rua trânsito transito festa* paredes vizinh* música musica"),
"safety": dict(
 en="safe* secure* security unsafe dangerous danger crime theft thief robbery sketchy lock*",
 es="segur* inseguro* peligro* robo* ladron* ladrón* delincuencia cerradura*",
 fr="sécur* secur* sûr sûre dangereu* danger vol voleur* cambriol* insécur* serrure*",
 de="sicher sichere sicheren sicherer sicherheit unsicher* gefährlich* gefahr kriminalität diebstahl dieb* einbruch*",
 pt="segur* inseguro* perig* assalto* roubo* ladr* crime* criminalidade fechadura*"),
"service": dict(
 en="service services staff reception receptionist checkin check checkout support response responded reply replied communication communicate* assistance",
 es="servicio* atención atencion personal recepción recepcion check checkin comunicación comunicacion respuesta* respond* ayuda asistencia trato",
 fr="service* accueil personnel réception reception check communication réponse* réactivité reactivite aide assistance contact*",
 de="service personal rezeption empfang check kommunikation antwort* reaktion hilfe unterstützung betreuung kontakt*",
 pt="serviço* servico* atendimento pessoal receção recepção check comunicação comunicacao resposta* ajuda apoio assistência contacto*"),
"listing_accuracy": dict(
 en="description described photo photos picture pictures accurate* accuracy inaccurate misleading listing listed advertised expectation* expected",
 es="descripción descripcion descrito descrita foto* imagen* imágenes anuncio publicado publicación exacto* fiel engañoso* esperaba* expectativas",
 fr="description décrit* decrit* photo* image* annonce conforme correspond* fidèle trompeur* attendu* attentes mensonger*",
 de="beschreibung beschrieben foto* fotos bild* bilder anzeige inserat entspricht entsprach entsprechen genau irreführend* erwartung* erwartet*",
 pt="descrição descricao descrito* foto* imagem imagens anúncio anuncio corresponde* fiel enganador* esperava* expectativas conforme"),
"overall_experience": dict(
 en="experience experiences stay stayed staying overall trip vacation holiday holidays visit visited weekend recommend* return again",
 es="experiencia* estancia* estadía estadia alojamiento viaje vacaciones visita* semana recomend* recomiend* volver* repetir*",
 fr="expérience* experience* séjour* sejour* voyage vacances visite* week recommand* revenir retourner globalement ensemble",
 de="erfahrung* aufenthalt* urlaub* reise* besuch* wochenende empfehl* wiederkommen insgesamt gesamt* rundum",
 pt="experiência* experiencia* estadia* estada viagem férias ferias visita* fim recomend* voltar* repetir* globalmente geral"),
}