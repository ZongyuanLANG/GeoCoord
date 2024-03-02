
#include "postgres.h"

#include "fmgr.h"
#include "libpq/pqformat.h"     /* needed for send/recv functions */

#include "access/hash.h"
#include "utils/builtins.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <regex.h>
#include <math.h>
#include <ctype.h>

#define TRUE 1
#define FALSE 0


PG_MODULE_MAGIC;

typedef struct GeoCoord
{
	int32 vl_len_;
	char format[FLEXIBLE_ARRAY_MEMBER];
}GeoCoord;

//define a new type to store locationName, latitudeValue, latitudeDirection, longitudeValue, longitudeDirection
struct normal_GeoCoord{
	char *LocationName;
	char LatitudeValue[20];
	char LatitudeDirection;
	char LongitudeValue[20];
	char LongitudeDirection;
};

//this function is used to check whether the input string is valid with regular expression
static
int regex_match(char * str, char * Pattern) {
	regex_t regex;
	int match = FALSE;
	if (regcomp(&regex, Pattern, REG_EXTENDED | REG_ICASE)) return -1;
	if (!regexec(&regex, str, 0, NULL, 0)) match = TRUE;
	regfree(&regex);
	return match;
}
static
int check_form(char * str){
	//form0:locationName,latitude,longitude
	int i = 0;
	int j = 0;
	char *parten0 = "^[a-zA-Z]+([ ][a-zA-Z]+)*,[+-]?(([1-8]?[0-9])(\\.[0-9]{1,10})?|90(\\.0{1,10})?)°[NS][ ,]"
					"[+-]?((([1-9]?[0-9]|1[0-7][0-9])(\\.[0-9]{1,10})?)|180(\\.0{1,10})?)°[WE]$";
	char *parten1 = "^[a-zA-Z]+([ ][a-zA-Z]+)*,[+-]?((([1-9]?[0-9]|1[0-7][0-9])(\\.[0-9]{1,10})?)|180(\\.0{1,10})?)°[WE][ ,]"
					"[+-]?(([1-8]?[0-9])(\\.[0-9]{1,10})?|90(\\.0{1,10})?)°[NS]$";
	i = regex_match(str, parten0);
	j = regex_match(str, parten1);
	return i + j;
}
static
struct normal_GeoCoord* normorize_GeoCoord(char *geostr) {
	//declare a new struct to store the normalized data
	struct normal_GeoCoord *n = palloc(sizeof(struct normal_GeoCoord));
	//flag to check which direction is first
	int direction_flag = 0;
	//comma number, detect whether there is only one comma,determine the form
	int commaNum = 0;
	//below three variables are used to store the normalized data
	char *location_name = NULL;
	char *secondEnd = NULL;
	char *first_comma = NULL;
	char *secondPart = NULL;

	//copy the input string, which can be modified
	int length = strlen(geostr) + 1;
	char *str = palloc(length);
	strcpy(str, geostr);

	//check which direction is first 1:latitude, 0: longitude
	if (str[length - 2] == 'W' || str[length - 2] == 'E') direction_flag = 1;
	//check whether there is only one comma
	for(int i = 0; i < strlen(str); i++)
		if(str[i] == ',') commaNum++;

	//split the first part of the string, which is locationName using comma
	first_comma = strchr(str, ',');
	*first_comma = '\0';
	//palloc the memory for locatio_name,with number first_comma - str;
	location_name = (char *) palloc(first_comma - str + 1);
	strcpy(location_name, str);
	//lower location_name
	for (int i = 0; i < strlen(location_name); i++)
		location_name[i] = tolower(location_name[i]);
	n->LocationName = location_name;
	//if the rest part is seperated by comma
	if(commaNum == 2){
		//if the rest part is latitude,Longitude
		if(direction_flag == 1){
			secondPart = strchr(first_comma + 1, ',');
			*(secondPart - 3) = '\0';
			//get latitudeDirection
			n->LatitudeDirection = *(secondPart - 1);
			//get latitudeValue
			strcpy(n->LatitudeValue,first_comma + 1);
			//get longitudeDirection
			secondEnd = str + length -2;
			n->LongitudeDirection = *(secondEnd);
			//get longitudeValue
			*(secondEnd -2) = '\0';
			strcpy(n->LongitudeValue, secondPart + 1);
		}
		else{
			//if the rest part is longitude,latitude
			secondPart = strchr(first_comma + 1, ',');
			*(secondPart - 3) = '\0';
			//get longitudeDirection
			n->LongitudeDirection = *(secondPart - 1);
			//get longitudeValue
			strcpy(n->LongitudeValue,first_comma + 1);
			//get latitudeDirection
			secondEnd = str + length -2;
			n->LatitudeDirection = *(secondEnd);
			//get latitudeValue
			*(secondEnd -2) = '\0';
			strcpy(n->LatitudeValue, secondPart + 1);
		}
	}
	else//if the rest part is seperated by space
	{
		//if the rest part is latitude,Longitude
		if(direction_flag == 1){
			secondPart = strchr(first_comma + 1, ' ');
			*(secondPart - 3) = '\0';
			//get latitudeDirection
			n->LatitudeDirection = *(secondPart - 1);
			//get latitudeValue
			strcpy(n->LatitudeValue,first_comma + 1);
			//get longitudeDirection
			secondEnd = str + length -2;
			n->LongitudeDirection = *(secondEnd);
			//get longitudeValue
			*(secondEnd -2) = '\0';
			strcpy(n->LongitudeValue, secondPart + 1);
		}
		else{
			//if the rest part is longitude,latitude
			secondPart = strchr(first_comma + 1, ' ');
			*(secondPart - 3) = '\0';
			//get longitudeDirection
			n->LongitudeDirection = *(secondPart - 1);
			//get longitudeValue
			strcpy(n->LongitudeValue,first_comma + 1);
			//get latitudeDirection
			secondEnd = str + length -2;
			n->LatitudeDirection = *(secondEnd);
			//get latitudeValue
			*(secondEnd -2) = '\0';
			strcpy(n->LatitudeValue, secondPart + 1);
		}
	}
	//free the memory
	pfree(str);
	return n;
}
static
void get_nomorized_data(struct normal_GeoCoord *n,char *result_str){
	sprintf(result_str,"%s%c%s%s%c%c%s%s%c%c",n->LocationName,',',n->LatitudeValue,"°",n->LatitudeDirection,',',
			n->LongitudeValue,"°",n->LongitudeDirection,'\0');
//	char comma[2] = ",";
//	char latitudeDirection[2];
//	char longitudeDirection[2];
//	latitudeDirection[0] =  n->LatitudeDirection;
//	latitudeDirection[1] = '\0';
//	longitudeDirection[0] = n->LongitudeDirection;
//	longitudeDirection[1] = '\0';
//
//	strcpy(result_str, n->LocationName);
//	strcat(result_str, comma);
//	strcat(result_str, n->LatitudeValue);
//	strcat(result_str, "°");
//	strcat(result_str, latitudeDirection);
//	strcat(result_str, comma);
//	strcat(result_str, n->LongitudeValue);
//	strcat(result_str, "°");
//	strcat(result_str, longitudeDirection);
}

PG_FUNCTION_INFO_V1(gcoord_in);

Datum
gcoord_in(PG_FUNCTION_ARGS) {
	char *str = PG_GETARG_CSTRING(0);
	GeoCoord *result = NULL;
	int length;
	char *result_data;
	if(check_form(str) == 0){
		ereport(ERROR,
				(errcode(ERRCODE_INVALID_TEXT_REPRESENTATION),
						errmsg("invalid input syntax for type %s: \"%s\"","GeoCoord",str)));
	}else {
		struct normal_GeoCoord *n;
		n = normorize_GeoCoord(str);
		result_data = palloc(strlen(n->LocationName) + strlen(n->LatitudeValue) + strlen(n->LongitudeValue) + 9);
		get_nomorized_data(n, result_data);
		length = strlen(result_data) + 1;
		result = palloc(VARHDRSZ + length);
		SET_VARSIZE(result, VARHDRSZ + length);
		memcpy(result->format, result_data, length);
	}
	PG_RETURN_POINTER(result);
}

PG_FUNCTION_INFO_V1(gcoord_out);

Datum
gcoord_out(PG_FUNCTION_ARGS)
{
	GeoCoord    *out = (GeoCoord *) PG_GETARG_POINTER(0);
	char	   *result;
	result = psprintf("%s", out->format);
	PG_RETURN_CSTRING(result);
}


//compare two GeoCoords
static
int myCompare(GeoCoord *g1, GeoCoord *g2) {
	struct normal_GeoCoord *n1 = (struct normal_GeoCoord*)palloc(sizeof(struct normal_GeoCoord));
	struct normal_GeoCoord *n2 = (struct normal_GeoCoord*)palloc(sizeof(struct normal_GeoCoord));
	n1 = normorize_GeoCoord(g1->format);
	n2 = normorize_GeoCoord(g2->format);
	//if the latitude of GeoCoord1 is closer to equator than the latitude of GeoCoord2
	if (atof(n1->LatitudeValue) < atof(n2->LatitudeValue)) {
		return 1;
	} else if (atof(n1->LongitudeValue) > atof(n2->LongitudeValue)) {
		return -1;
	} else {//If they have the same latitude who is in the north who is greater
		if (n1->LatitudeDirection == 'N' && n2->LatitudeDirection == 'S') return 1;
		else if (n1->LatitudeDirection == 'S' && n2->LatitudeDirection == 'N') return -1;
		else {//if they have the same latitude and direction
			//if the longitude of GeoCoord1 is closer to prime meridian than the longitude of GeoCoord2
			if (atof(n1->LongitudeValue) < atof(n2->LongitudeValue)) {
				return 1;
			} else if (atof(n1->LongitudeValue) > atof(n2->LongitudeValue)){
				return -1;
			} else {//If they have the same longitude who is in the east who is greater
				if (n1->LongitudeDirection == 'E' && n2->LongitudeDirection == 'W') return 1;
				else if (n1->LongitudeDirection == 'W' && n2->LongitudeDirection == 'E') return -1;
				else {//if they have the same longitude and direction
					//if the LocationName of GeoCoord1 is lexically greater than the LocationName of GeoCoord2
					if (strcmp(n1->LocationName, n2->LocationName) < 0) {
						return 1;
					} else if (strcmp(n1->LocationName, n2->LocationName) > 0) {
						return -1;
					} else return 0;

				}
			}
		}
	}
}

PG_FUNCTION_INFO_V1(gcoord_abs_lt);

Datum
gcoord_abs_lt(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	GeoCoord    *b = (GeoCoord *) PG_GETARG_POINTER(1);

	PG_RETURN_BOOL(myCompare(a, b) < 0);
}

PG_FUNCTION_INFO_V1(gcoord_abs_le);

Datum
gcoord_abs_le(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	GeoCoord    *b = (GeoCoord *) PG_GETARG_POINTER(1);

	PG_RETURN_BOOL(myCompare(a, b) <= 0);
}

PG_FUNCTION_INFO_V1(gcoord_abs_eq);

Datum
gcoord_abs_eq(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	GeoCoord    *b = (GeoCoord *) PG_GETARG_POINTER(1);

	PG_RETURN_BOOL(myCompare(a, b) == 0);
}
PG_FUNCTION_INFO_V1(gcoord_abs_neq);

Datum
gcoord_abs_neq(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	GeoCoord    *b = (GeoCoord *) PG_GETARG_POINTER(1);

	PG_RETURN_BOOL(myCompare(a, b) != 0);
}

PG_FUNCTION_INFO_V1(gcoord_abs_ge);

Datum
gcoord_abs_ge(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	GeoCoord    *b = (GeoCoord *) PG_GETARG_POINTER(1);

	PG_RETURN_BOOL(myCompare(a, b) >= 0);
}


PG_FUNCTION_INFO_V1(gcoord_abs_gt);

Datum
gcoord_abs_gt(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	GeoCoord    *b = (GeoCoord *) PG_GETARG_POINTER(1);

	PG_RETURN_BOOL(myCompare(a, b) > 0);
}

PG_FUNCTION_INFO_V1(gcoord_abs_cmp);
Datum
gcoord_abs_cmp(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	GeoCoord    *b = (GeoCoord *) PG_GETARG_POINTER(1);

	PG_RETURN_INT32(myCompare(a, b));
}

//judge if they are in the same time zone
static
int judge_stz(GeoCoord *g1, GeoCoord *g2){
	struct normal_GeoCoord *n1 = (struct normal_GeoCoord*)palloc(sizeof(struct normal_GeoCoord));
	struct normal_GeoCoord *n2 = (struct normal_GeoCoord*)palloc(sizeof(struct normal_GeoCoord));
	n1 = normorize_GeoCoord(g1->format);
	n2 = normorize_GeoCoord(g2->format);
	if((int)(atof(n1->LatitudeValue)/15) == (int)(atof(n2->LatitudeValue)/15))
		return 1;
	else return 0;
}


PG_FUNCTION_INFO_V1(gcoord_stz);

Datum
gcoord_stz(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	GeoCoord    *b = (GeoCoord *) PG_GETARG_POINTER(1);

	PG_RETURN_BOOL(judge_stz(a,b) == 1);
}


PG_FUNCTION_INFO_V1(gcoord_nstz);

Datum
gcoord_nstz(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	GeoCoord    *b = (GeoCoord *) PG_GETARG_POINTER(1);

	PG_RETURN_BOOL(judge_stz(a,b) == 0);
}

static
int myfloor(int x){
	int result = x;
	if(x%10 != 0)
		result = x - x%10;
	if(x%100 != 0)
		result = x - x%100;
	if(x%1000 != 0)
		result = x - x%1000;
	if(x%10000 != 0)
		result = x - x%10000;
	return result;
}
static
char *myConvert2DMS(struct normal_GeoCoord *n){
	char *result = palloc(300);
	int latitude;
	int longitude;
	int latitudeD;
	int latitudeM;
	int latitudeS;
	int longitudeD;
	int longitudeM;
	int longitudeS;
	char latitudeD_str[10];
	char latitudeM_str[10];
	char latitudeS_str[10];
	char longitudeD_str[10];
	char longitudeM_str[10];
	char longitudeS_str[10];
	char comma[2] = ",";
	char latitudeDirection[2];
	char longitudeDirection[2];
	latitudeDirection[0] =  n->LatitudeDirection;
	latitudeDirection[1] = '\0';
	longitudeDirection[0] = n->LongitudeDirection;
	longitudeDirection[1] = '\0';

	latitude = (int)10000 * atof(n->LatitudeValue);
	latitudeD = myfloor(latitude);
	latitudeM = myfloor(60*(latitude - latitudeD));
	latitudeS = myfloor(3600*(latitude - latitudeD - latitudeM/60));

	sprintf(latitudeD_str, "%d", latitudeD/10000);
	sprintf(latitudeM_str,"%d",latitudeM/10000);
	sprintf(latitudeS_str,"%d",latitudeS/10000);

	longitude = (int)10000 * atof(n->LongitudeValue);
	longitudeD = myfloor(longitude);
	longitudeM = myfloor(60*(longitude - longitudeD));
	longitudeS = myfloor(3600*(longitude - longitudeD - longitudeM/60));

	sprintf(longitudeD_str, "%d", longitudeD/10000);
	sprintf(longitudeM_str,"%d",longitudeM/10000);
	sprintf(longitudeS_str,"%d",longitudeS/10000);

	strcpy(result, n->LocationName);
	strcat(result, comma);
	//printf("%s",result);
	strcat(result, latitudeD_str);
	strcat(result, "°");
	//printf("%s",result);
	if(latitudeM != 0){
		strcat(result, latitudeM_str);
		strcat(result, "\'");
		//printf("%s",result);
		if(latitudeS != 0){
			strcat(result, latitudeS_str);
			strcat(result, "\"");
		}
	}
	strcat(result, latitudeDirection);

	strcat(result,comma);
	strcat(result, longitudeD_str);
	strcat(result, "°");

	if(longitudeM != 0){
		strcat(result, longitudeM_str);
		strcat(result, "\'");
		if(longitudeS != 0){
			strcat(result, longitudeS_str);
			strcat(result, "\"");
		}
	}
	strcat(result, longitudeDirection);
	return result;
}


PG_FUNCTION_INFO_V1(gcoord_convert2dms);
Datum
gcoord_convert2dms(PG_FUNCTION_ARGS)
{
	GeoCoord    *a = (GeoCoord *) PG_GETARG_POINTER(0);
	struct normal_GeoCoord *n = palloc(sizeof(struct normal_GeoCoord));
	n = normorize_GeoCoord(a->format);
	char *result_data;
	result_data = myConvert2DMS(n);
	pfree(n);
	PG_RETURN_CSTRING(result_data);
}


PG_FUNCTION_INFO_V1(hash_gcoord);
Datum
hash_gcoord(PG_FUNCTION_ARGS)
{
	GeoCoord  *g = (GeoCoord *) PG_GETARG_POINTER(0);
	int length = strlen(g->format);
	PG_RETURN_INT32(DatumGetUInt32(hash_any((const unsigned char *)g->format, length)));
}
